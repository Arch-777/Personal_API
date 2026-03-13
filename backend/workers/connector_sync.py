from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from api.core.config import get_settings
from api.core.db import SessionLocal
from api.models.connector import Connector
from api.models.item import Item
from normalizer.base import BaseNormalizer, NormalizedItem
from normalizer.drive import DriveNormalizer
from normalizer.gcal import GCalNormalizer
from normalizer.gmail import GmailNormalizer
from normalizer.notion import NotionNormalizer
from normalizer.spotify import SpotifyNormalizer
from normalizer.whatsapp import WhatsAppNormalizer


NOTION_VERSION = "2022-06-28"
HTTP_TIMEOUT_SECONDS = 20.0
_FILENAME_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")

NORMALIZERS: dict[str, BaseNormalizer] = {
    "gmail": GmailNormalizer(),
    "drive": DriveNormalizer(),
    "gcal": GCalNormalizer(),
    "whatsapp": WhatsAppNormalizer(),
    "notion": NotionNormalizer(),
    "spotify": SpotifyNormalizer(),
}


@dataclass(slots=True)
class SyncRunResult:
    platform: str
    connector_id: str
    user_id: str
    items_upserted: int
    next_cursor: str


def run_connector_sync(platform: str, connector_id: str, user_id: str, cursor: str | None = None) -> dict[str, Any]:
    parsed_connector_id = uuid.UUID(connector_id)
    parsed_user_id = uuid.UUID(user_id)

    _mark_sync_started(parsed_connector_id, parsed_user_id)

    try:
        with SessionLocal() as db:
            connector = _get_connector(db, parsed_connector_id, parsed_user_id, platform)
            tokens = _resolve_tokens(connector)

            source_cursor = cursor if cursor is not None else connector.sync_cursor
            raw_records, next_cursor = _fetch_platform_records(
                platform=platform,
                connector=connector,
                source_cursor=source_cursor,
                access_token=tokens["access_token"],
            )
            normalized_items = _normalize_records(platform, raw_records)
            rows = _persist_normalized_items(connector, normalized_items, source_cursor)
            upserted_item_ids = _upsert_items(db, rows)

            connector.sync_cursor = next_cursor
            connector.last_synced = datetime.now(UTC)
            connector.status = "connected"
            connector.error_message = None
            db.commit()

        return {
            "status": "completed",
            "platform": platform,
            "connector_id": connector_id,
            "user_id": user_id,
            "records_fetched": len(raw_records),
            "records_normalized": len(normalized_items),
            "items_upserted": len(upserted_item_ids),
            "next_cursor": next_cursor,
            "item_ids": [str(item_id) for item_id in upserted_item_ids],
        }
    except Exception as exc:
        _mark_sync_failed(parsed_connector_id, parsed_user_id, str(exc))
        raise


def _get_connector(db, connector_id: uuid.UUID, user_id: uuid.UUID, platform: str) -> Connector:
    connector = db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.user_id == user_id,
            Connector.platform == platform,
        )
    ).scalar_one_or_none()
    if connector is None:
        raise ValueError(f"Connector not found for platform '{platform}'")
    return connector


def _resolve_tokens(connector: Connector) -> dict[str, str | None]:
    access_token = connector.encrypted_access_token.strip()
    if not access_token:
        raise ValueError("Connector access token is missing")

    return {
        "access_token": access_token,
        "refresh_token": connector.encrypted_refresh_token,
    }


def _parse_cursor(raw_cursor: str | None) -> int:
    if raw_cursor is None:
        return 0
    try:
        parsed = int(raw_cursor)
    except ValueError:
        return 0
    return max(parsed, 0)


def _fetch_platform_records(
    platform: str,
    connector: Connector,
    source_cursor: str | None,
    access_token: str,
) -> tuple[list[dict[str, Any]], str]:
    metadata = connector.metadata_json if isinstance(connector.metadata_json, dict) else {}
    seeded_records = metadata.get("sample_records")
    if isinstance(seeded_records, list):
        next_cursor = str(metadata.get("sample_next_cursor") or (_parse_cursor(source_cursor) + len(seeded_records)))
        return [record for record in seeded_records if isinstance(record, dict)], next_cursor

    if platform == "gmail":
        return _fetch_gmail_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "drive":
        return _fetch_drive_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "gcal":
        return _fetch_gcal_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "notion":
        return _fetch_notion_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "spotify":
        return _fetch_spotify_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "whatsapp":
        return _fetch_whatsapp_records(access_token=access_token, source_cursor=source_cursor, connector=connector)
    raise ValueError(f"Unsupported connector platform '{platform}'")


def _fetch_gmail_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {"maxResults": 25}
    if source_cursor:
        params["pageToken"] = source_cursor

    payload = _http_get_json(
        url="https://gmail.googleapis.com/gmail/v1/users/me/messages",
        access_token=access_token,
        params=params,
    )
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    rows: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = message.get("id")
        if not message_id:
            continue
        detail = _http_get_json(
            url=f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            access_token=access_token,
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
        )
        if isinstance(detail, dict):
            rows.append(detail)

    next_cursor = _extract_next_cursor(payload, source_cursor)
    return rows, next_cursor


def _fetch_drive_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {
        "pageSize": 25,
        "fields": "nextPageToken,files(id,name,mimeType,description,modifiedTime,createdTime,owners(displayName,emailAddress),webViewLink)",
        "orderBy": "modifiedTime desc",
    }
    if source_cursor:
        params["pageToken"] = source_cursor

    payload = _http_get_json(
        url="https://www.googleapis.com/drive/v3/files",
        access_token=access_token,
        params=params,
    )
    rows = payload.get("files") if isinstance(payload.get("files"), list) else []
    next_cursor = _extract_next_cursor(payload, source_cursor)
    return [row for row in rows if isinstance(row, dict)], next_cursor


def _fetch_gcal_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {
        "maxResults": 25,
        "singleEvents": True,
        "orderBy": "updated",
    }
    if source_cursor:
        params["pageToken"] = source_cursor

    payload = _http_get_json(
        url="https://www.googleapis.com/calendar/v3/calendars/primary/events",
        access_token=access_token,
        params=params,
    )
    rows = payload.get("items") if isinstance(payload.get("items"), list) else []
    next_cursor = _extract_next_cursor(payload, source_cursor)
    return [row for row in rows if isinstance(row, dict)], next_cursor


def _fetch_notion_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    body: dict[str, Any] = {"page_size": 25}
    if source_cursor:
        body["start_cursor"] = source_cursor

    payload = _http_post_json(
        url="https://api.notion.com/v1/search",
        access_token=access_token,
        json_body=body,
        headers={"Notion-Version": NOTION_VERSION},
    )
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    next_cursor = _extract_next_cursor(payload, source_cursor)
    return [row for row in rows if isinstance(row, dict)], next_cursor


def _fetch_spotify_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {"limit": 25}
    if source_cursor:
        params["after"] = source_cursor

    payload = _http_get_json(
        url="https://api.spotify.com/v1/me/player/recently-played",
        access_token=access_token,
        params=params,
    )
    rows = payload.get("items") if isinstance(payload.get("items"), list) else []
    next_cursor = _extract_next_cursor(payload, source_cursor)
    return [row for row in rows if isinstance(row, dict)], next_cursor


def _fetch_whatsapp_records(
    access_token: str,
    source_cursor: str | None,
    connector: Connector,
) -> tuple[list[dict[str, Any]], str]:
    metadata = connector.metadata_json if isinstance(connector.metadata_json, dict) else {}
    endpoint = metadata.get("messages_endpoint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        return [], str(source_cursor or "0")

    params: dict[str, Any] = {}
    if source_cursor:
        params["cursor"] = source_cursor

    payload = _http_get_json(
        url=endpoint,
        access_token=access_token,
        params=params,
    )
    rows = _extract_first_record_list(payload)
    next_cursor = _extract_next_cursor(payload, source_cursor)
    return rows, next_cursor


def _normalize_records(platform: str, raw_records: list[dict[str, Any]]) -> list[NormalizedItem]:
    normalizer = NORMALIZERS.get(platform)
    if normalizer is None:
        raise ValueError(f"No normalizer configured for platform '{platform}'")
    return normalizer.normalize_records(raw_records)


def _persist_normalized_items(
    connector: Connector,
    normalized_items: list[NormalizedItem],
    source_cursor: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in normalized_items:
        file_path = _store_item_file(user_id=connector.user_id, platform=connector.platform, item=item)
        metadata = dict(item.metadata_json)
        metadata.update(
            {
                "connector_id": str(connector.id),
                "cursor": source_cursor,
                "ingestion_mode": "api",
                "file_path": file_path,
            }
        )
        rows.append(
            {
                "user_id": connector.user_id,
                "type": item.type,
                "source": item.source,
                "source_id": item.source_id,
                "title": item.title,
                "sender_name": item.sender_name,
                "sender_email": item.sender_email,
                "content": item.content,
                "summary": item.summary,
                "metadata_json": metadata,
                "item_date": item.item_date,
                "file_path": file_path,
            }
        )
    return rows


def _store_item_file(user_id: uuid.UUID, platform: str, item: NormalizedItem) -> str:
    settings = get_settings()
    root = Path(settings.user_data_root).expanduser().resolve()
    relative_dir = Path("users") / str(user_id) / "data" / platform
    target_dir = root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = _deterministic_filename(item.type, item.source_id)
    target_file = target_dir / filename
    payload = {
        "type": item.type,
        "source": item.source,
        "source_id": item.source_id,
        "title": item.title,
        "sender_name": item.sender_name,
        "sender_email": item.sender_email,
        "content": item.content,
        "summary": item.summary,
        "metadata": item.metadata_json,
        "item_date": item.item_date.isoformat() if item.item_date else None,
        "raw_record": item.raw_record,
    }
    target_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str), encoding="utf-8")

    return f"/users/{user_id}/data/{platform}/{filename}"


def _deterministic_filename(item_type: str, source_id: str) -> str:
    safe_source = _FILENAME_SAFE_PATTERN.sub("_", source_id).strip("._") or "item"
    safe_source = safe_source[:80]
    item_prefix = _FILENAME_SAFE_PATTERN.sub("_", item_type).strip("._") or "item"
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:10]
    return f"{item_prefix}_{safe_source}_{digest}.json"


def _http_get_json(
    url: str,
    access_token: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    merged_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    if headers:
        merged_headers.update(headers)

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params, headers=merged_headers)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response payload type from {url}")
    return data


def _http_post_json(
    url: str,
    access_token: str,
    json_body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    merged_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        merged_headers.update(headers)

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=json_body, headers=merged_headers)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response payload type from {url}")
    return data


def _extract_next_cursor(payload: dict[str, Any], current_cursor: str | None) -> str:
    for key in ["next_cursor", "nextPageToken", "next_page_token", "cursor", "pageToken"]:
        value = payload.get(key)
        if value:
            return str(value)

    cursors = payload.get("cursors")
    if isinstance(cursors, dict):
        for key in ["after", "next"]:
            value = cursors.get(key)
            if value:
                return str(value)

    return str(current_cursor or "0")


def _extract_first_record_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ["items", "results", "data", "messages", "files", "events"]:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _upsert_items(db, rows: list[dict[str, Any]]) -> list[uuid.UUID]:
    if not rows:
        return []

    stmt = insert(Item).values(rows)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=[Item.user_id, Item.source, Item.source_id],
        set_={
            "type": stmt.excluded.type,
            "title": stmt.excluded.title,
            "sender_name": stmt.excluded.sender_name,
            "sender_email": stmt.excluded.sender_email,
            "content": stmt.excluded.content,
            "summary": stmt.excluded.summary,
            "metadata": stmt.excluded.metadata,
            "item_date": stmt.excluded.item_date,
            "file_path": stmt.excluded.file_path,
            "updated_at": datetime.now(UTC),
        },
    ).returning(Item.id)

    result = db.execute(upsert_stmt)
    return list(result.scalars().all())


def _mark_sync_started(connector_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        connector = db.execute(
            select(Connector).where(Connector.id == connector_id, Connector.user_id == user_id)
        ).scalar_one_or_none()
        if connector is None:
            return

        connector.status = "syncing"
        connector.error_message = None
        db.commit()


def _mark_sync_failed(connector_id: uuid.UUID, user_id: uuid.UUID, message: str) -> None:
    with SessionLocal() as db:
        connector = db.execute(
            select(Connector).where(Connector.id == connector_id, Connector.user_id == user_id)
        ).scalar_one_or_none()
        if connector is None:
            return

        connector.status = "error"
        connector.error_message = message[:500]
        db.commit()
