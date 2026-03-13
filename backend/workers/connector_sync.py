from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from api.core.config import get_settings
from api.core.db import SessionLocal
from api.models.connector import Connector
from api.models.item import Item
from normalizer.base import BaseNormalizer, NormalizedItem
from rag.indexer import index_item_chunks

def _broadcast(user_id: str, event: str, data: dict[str, Any]) -> None:
    """Best-effort broadcast to WebSocket clients. Silently skips if unavailable."""
    try:
        from api.routers.ws import broadcast_sync_event
        broadcast_sync_event(user_id, event, data)
    except Exception:  # noqa: BLE001
        pass
from normalizer.drive import DriveNormalizer
from normalizer.gcal import GCalNormalizer
from normalizer.gmail import GmailNormalizer
from normalizer.notion import NotionNormalizer
from normalizer.slack import SlackNormalizer
from normalizer.spotify import SpotifyNormalizer
from normalizer.whatsapp import WhatsAppNormalizer


NOTION_VERSION = "2022-06-28"
HTTP_TIMEOUT_SECONDS = 20.0
_FILENAME_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")
NOTION_MAX_PAGE_ENRICH = 20
NOTION_MAX_DATABASES = 5
NOTION_MAX_DATABASE_ROWS = 20

NORMALIZERS: dict[str, BaseNormalizer] = {
    "gmail": GmailNormalizer(),
    "drive": DriveNormalizer(),
    "gcal": GCalNormalizer(),
    "whatsapp": WhatsAppNormalizer(),
    "notion": NotionNormalizer(),
    "slack": SlackNormalizer(),
    "spotify": SpotifyNormalizer(),
}

logger = logging.getLogger(__name__)


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
    _broadcast(user_id, "sync.started", {"platform": platform, "connector_id": connector_id})

    try:
        with SessionLocal() as db:
            connector = _get_connector(db, parsed_connector_id, parsed_user_id, platform)
            if platform in {"gmail", "drive", "gcal"}:
                _maybe_refresh_google_token(db, connector)
            if platform == "spotify":
                _maybe_refresh_spotify_token(db, connector)
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
            _inline_index_items(db, upserted_item_ids, parsed_user_id)

            connector.sync_cursor = next_cursor
            connector.last_synced = datetime.now(UTC)
            connector.status = "connected"
            connector.error_message = None
            db.commit()

        _enqueue_indexing_tasks(item_ids=upserted_item_ids, user_id=parsed_user_id, source=platform)

        _broadcast(user_id, "sync.completed", {
            "platform": platform,
            "connector_id": connector_id,
            "items_upserted": len(upserted_item_ids),
        })

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
        _broadcast(user_id, "sync.failed", {"platform": platform, "connector_id": connector_id, "error": str(exc)})
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


def _maybe_refresh_spotify_token(db: Any, connector: Connector) -> None:
    """Refresh the Spotify access token when it is expired or expires within 5 minutes."""
    settings = get_settings()
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        return  # OAuth not configured; dev/bootstrap tokens used as-is.

    if connector.token_expires_at is None:
        return

    expiry = connector.token_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry > datetime.now(UTC) + timedelta(minutes=5):
        return  # Still valid.

    refresh_token = connector.encrypted_refresh_token
    if not refresh_token:
        raise ValueError("Spotify access token expired and no refresh token is stored")

    credentials = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()

    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        token_data = response.json()

    new_access_token = token_data.get("access_token")
    if not new_access_token:
        raise ValueError("Spotify token refresh returned an empty access_token")

    expires_in = int(token_data.get("expires_in", 3600))
    connector.encrypted_access_token = new_access_token
    connector.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    new_refresh = token_data.get("refresh_token")
    if new_refresh:
        connector.encrypted_refresh_token = new_refresh
    db.commit()


def _maybe_refresh_google_token(db: Any, connector: Connector) -> None:
    """Refresh Google OAuth access token when expired or close to expiring."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        return

    if connector.token_expires_at is None:
        return

    expiry = connector.token_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry > datetime.now(UTC) + timedelta(minutes=5):
        return

    refresh_token = connector.encrypted_refresh_token
    if not refresh_token:
        raise ValueError("Google access token expired and no refresh token is stored")

    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

    new_access_token = token_data.get("access_token")
    if not new_access_token:
        raise ValueError("Google token refresh returned an empty access_token")

    expires_in = int(token_data.get("expires_in", 3600))
    connector.encrypted_access_token = new_access_token
    connector.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    db.commit()


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


def _has_cursor_value(raw_cursor: str | None) -> bool:
    if raw_cursor is None:
        return False
    normalized = raw_cursor.strip()
    return normalized not in {"", "0"}


def _parse_state_cursor(raw_cursor: str | None) -> dict[str, str]:
    if not _has_cursor_value(raw_cursor):
        return {}

    normalized = raw_cursor.strip()
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return {"page_token": normalized}

    if not isinstance(parsed, dict):
        return {}

    state: dict[str, str] = {}
    for key in ["page_token", "updated_after", "sync_token"]:
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            state[key] = value.strip()
    return state


def _encode_state_cursor(state: dict[str, str]) -> str:
    compact_state = {k: v for k, v in state.items() if isinstance(v, str) and v.strip()}
    if not compact_state:
        return ""
    return json.dumps(compact_state, sort_keys=True)


def _max_datetime_value(rows: list[dict[str, Any]], key: str) -> str:
    values = [str(row.get(key)).strip() for row in rows if isinstance(row.get(key), str) and str(row.get(key)).strip()]
    if not values:
        return ""
    return max(values)


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
    if platform == "slack":
        return _fetch_slack_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "spotify":
        return _fetch_spotify_records(access_token=access_token, source_cursor=source_cursor)
    if platform == "whatsapp":
        return _fetch_whatsapp_records(access_token=access_token, source_cursor=source_cursor, connector=connector)
    raise ValueError(f"Unsupported connector platform '{platform}'")


def _fetch_gmail_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {"maxResults": 25}
    if _has_cursor_value(source_cursor):
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

    next_cursor = str(payload.get("nextPageToken") or "")
    return rows, next_cursor


def _fetch_drive_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    cursor_state = _parse_state_cursor(source_cursor)
    page_token = cursor_state.get("page_token")
    updated_after = cursor_state.get("updated_after")

    params: dict[str, Any] = {
        "pageSize": 100,
        "fields": "nextPageToken,files(id,name,mimeType,description,modifiedTime,createdTime,owners(displayName,emailAddress),webViewLink)",
        "orderBy": "modifiedTime asc",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "q": "trashed = false",
    }
    if updated_after and not page_token:
        params["q"] = f"trashed = false and modifiedTime > '{updated_after}'"
    if page_token:
        params["pageToken"] = page_token

    payload = _http_get_json(
        url="https://www.googleapis.com/drive/v3/files",
        access_token=access_token,
        params=params,
    )
    rows = [row for row in (payload.get("files") if isinstance(payload.get("files"), list) else []) if isinstance(row, dict)]

    next_page_token = payload.get("nextPageToken")
    max_modified_time = _max_datetime_value(rows, "modifiedTime")
    if next_page_token:
        next_cursor = _encode_state_cursor(
            {
                "page_token": str(next_page_token),
                "updated_after": updated_after or max_modified_time,
            }
        )
    else:
        next_cursor = _encode_state_cursor({"updated_after": max_modified_time or updated_after or ""})

    return rows, next_cursor


def _fetch_gcal_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    cursor_state = _parse_state_cursor(source_cursor)
    page_token = cursor_state.get("page_token")
    sync_token = cursor_state.get("sync_token")
    updated_after = cursor_state.get("updated_after")

    params: dict[str, Any]
    if sync_token and not page_token:
        params = {
            "maxResults": 250,
            "singleEvents": True,
            "syncToken": sync_token,
        }
    else:
        params = {
            "maxResults": 250,
            "singleEvents": True,
            "orderBy": "updated",
        }
        if updated_after and not page_token:
            params["updatedMin"] = updated_after

    if page_token:
        params["pageToken"] = page_token

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    try:
        payload = _http_get_json(url=url, access_token=access_token, params=params)
    except httpx.HTTPStatusError as exc:
        # Google invalidates sync tokens; fall back to updatedMin-based incremental pull.
        if params.get("syncToken") and exc.response is not None and exc.response.status_code == 410:
            fallback_params: dict[str, Any] = {
                "maxResults": 250,
                "singleEvents": True,
                "orderBy": "updated",
            }
            if updated_after:
                fallback_params["updatedMin"] = updated_after
            payload = _http_get_json(url=url, access_token=access_token, params=fallback_params)
            params = fallback_params
            sync_token = ""
        else:
            raise

    rows = [row for row in (payload.get("items") if isinstance(payload.get("items"), list) else []) if isinstance(row, dict)]
    next_page_token = payload.get("nextPageToken")
    next_sync_token = payload.get("nextSyncToken")
    max_updated = _max_datetime_value(rows, "updated")

    if next_page_token:
        next_cursor = _encode_state_cursor(
            {
                "page_token": str(next_page_token),
                "sync_token": sync_token,
                "updated_after": updated_after,
            }
        )
    else:
        next_cursor = _encode_state_cursor(
            {
                "sync_token": str(next_sync_token) if isinstance(next_sync_token, str) else sync_token,
                "updated_after": max_updated or updated_after or "",
            }
        )

    return rows, next_cursor


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
    notion_rows = [row for row in rows if isinstance(row, dict)]

    # Enrich top-level pages with block text and expand databases into recent rows.
    enriched_rows = _enrich_notion_rows(access_token=access_token, rows=notion_rows)

    next_cursor = _extract_next_cursor(payload, source_cursor)
    return enriched_rows, next_cursor


def _enrich_notion_rows(access_token: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    page_count = 0
    database_count = 0

    for row in rows:
        object_type = row.get("object")
        if object_type == "page":
            if page_count < NOTION_MAX_PAGE_ENRICH:
                page_id = row.get("id")
                if isinstance(page_id, str) and page_id:
                    row = dict(row)
                    row["plain_text"] = _fetch_notion_page_plain_text(access_token=access_token, page_id=page_id)
                page_count += 1
            enriched.append(row)
            continue

        if object_type == "database":
            enriched.append(row)
            if database_count < NOTION_MAX_DATABASES:
                database_id = row.get("id")
                if isinstance(database_id, str) and database_id:
                    enriched.extend(
                        _fetch_notion_database_rows(access_token=access_token, database_id=database_id)
                    )
                database_count += 1
            continue

        enriched.append(row)

    return enriched


def _fetch_notion_page_plain_text(access_token: str, page_id: str) -> str:
    try:
        payload = _http_get_json(
            url=f"https://api.notion.com/v1/blocks/{page_id}/children",
            access_token=access_token,
            params={"page_size": 100},
            headers={"Notion-Version": NOTION_VERSION},
        )
    except Exception:  # noqa: BLE001
        return ""

    blocks = payload.get("results") if isinstance(payload.get("results"), list) else []
    return _extract_notion_plain_text(blocks)


def _fetch_notion_database_rows(access_token: str, database_id: str) -> list[dict[str, Any]]:
    try:
        payload = _http_post_json(
            url=f"https://api.notion.com/v1/databases/{database_id}/query",
            access_token=access_token,
            json_body={"page_size": NOTION_MAX_DATABASE_ROWS},
            headers={"Notion-Version": NOTION_VERSION},
        )
    except Exception:  # noqa: BLE001
        return []

    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    rows: list[dict[str, Any]] = []
    for page in results:
        if not isinstance(page, dict):
            continue
        page_id = page.get("id")
        row = dict(page)
        if isinstance(page_id, str) and page_id:
            row["plain_text"] = _fetch_notion_page_plain_text(access_token=access_token, page_id=page_id)
            row["database_id"] = database_id
        rows.append(row)
    return rows


def _extract_notion_plain_text(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if not isinstance(block_type, str):
            continue
        payload = block.get(block_type)
        if not isinstance(payload, dict):
            continue
        rich_text = payload.get("rich_text") if isinstance(payload.get("rich_text"), list) else []
        text_parts: list[str] = []
        for token in rich_text:
            if not isinstance(token, dict):
                continue
            plain = token.get("plain_text")
            if isinstance(plain, str) and plain.strip():
                text_parts.append(plain.strip())
        if text_parts:
            lines.append(" ".join(text_parts))
    return "\n".join(lines)


def _fetch_spotify_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    # Fetch recently-played (cursor-based, incremental).
    params: dict[str, Any] = {"limit": 50}
    if source_cursor:
        params["after"] = source_cursor

    payload = _http_get_json(
        url="https://api.spotify.com/v1/me/player/recently-played",
        access_token=access_token,
        params=params,
    )
    rp_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    rp_rows = [
        dict(row, _record_type="recently_played")
        for row in rp_items
        if isinstance(row, dict)
    ]

    # Advance cursor: cursors.after is the timestamp of the newest track in the batch.
    cursors = payload.get("cursors")
    next_cursor = (
        str(cursors["after"])
        if isinstance(cursors, dict) and cursors.get("after")
        else _extract_next_cursor(payload, source_cursor)
    )

    # Fetch liked/saved songs as well (first 50, best-effort).
    liked_rows: list[dict[str, Any]] = []
    try:
        liked_payload = _http_get_json(
            url="https://api.spotify.com/v1/me/tracks",
            access_token=access_token,
            params={"limit": 50, "offset": 0},
        )
        liked_items = liked_payload.get("items") if isinstance(liked_payload.get("items"), list) else []
        liked_rows = [
            dict(item, _record_type="liked")
            for item in liked_items
            if isinstance(item, dict)
        ]
    except Exception:  # noqa: BLE001 — liked songs fetch is non-critical
        pass

    return rp_rows + liked_rows, next_cursor


def _fetch_slack_records(access_token: str, source_cursor: str | None) -> tuple[list[dict[str, Any]], str]:
    cursor_state = _parse_slack_cursor(source_cursor)
    latest_ts = _normalize_slack_ts(cursor_state.get("latest_ts"))

    conversations_payload = _ensure_slack_ok(
        _http_get_json(
            url="https://slack.com/api/conversations.list",
            access_token=access_token,
            params={
                "limit": 100,
                "types": "public_channel,private_channel,im,mpim",
                "exclude_archived": "true",
            },
        ),
        url="https://slack.com/api/conversations.list",
    )
    conversations = conversations_payload.get("channels") if isinstance(conversations_payload.get("channels"), list) else []

    user_cache: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    newest_ts = latest_ts

    for conversation in conversations[:25]:
        if not isinstance(conversation, dict):
            continue
        channel_id = conversation.get("id")
        if not isinstance(channel_id, str) or not channel_id:
            continue

        params: dict[str, Any] = {"channel": channel_id, "limit": 20}
        if latest_ts:
            params["oldest"] = latest_ts

        history_payload = _ensure_slack_ok(
            _http_get_json(
                url="https://slack.com/api/conversations.history",
                access_token=access_token,
                params=params,
            ),
            url="https://slack.com/api/conversations.history",
        )
        messages = history_payload.get("messages") if isinstance(history_payload.get("messages"), list) else []
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("type") != "message" or message.get("hidden") is True:
                continue

            user_id = message.get("user") if isinstance(message.get("user"), str) else None
            profile = _fetch_slack_user_profile(access_token=access_token, user_id=user_id, cache=user_cache)
            enriched = dict(message)
            enriched["_channel"] = {
                "id": channel_id,
                "name": conversation.get("name"),
                "is_im": conversation.get("is_im"),
                "is_private": conversation.get("is_private"),
                "is_mpim": conversation.get("is_mpim"),
            }
            if profile:
                enriched["_user_profile"] = profile
            rows.append(enriched)

            message_ts = _normalize_slack_ts(message.get("ts"))
            if message_ts and (not newest_ts or float(message_ts) > float(newest_ts)):
                newest_ts = message_ts

    next_cursor_payload = {"latest_ts": newest_ts or latest_ts or "0"}
    return rows, json.dumps(next_cursor_payload, sort_keys=True)


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


def _parse_slack_cursor(source_cursor: str | None) -> dict[str, str]:
    if source_cursor is None or source_cursor.strip() in {"", "0"}:
        return {}
    try:
        payload = json.loads(source_cursor)
    except json.JSONDecodeError:
        return {"latest_ts": source_cursor}
    if not isinstance(payload, dict):
        return {}
    latest_ts = payload.get("latest_ts")
    return {"latest_ts": str(latest_ts)} if latest_ts else {}


def _normalize_slack_ts(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _fetch_slack_user_profile(access_token: str, user_id: str | None, cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not user_id:
        return None
    if user_id in cache:
        return cache[user_id]

    try:
        payload = _ensure_slack_ok(
            _http_get_json(
                url="https://slack.com/api/users.info",
                access_token=access_token,
                params={"user": user_id},
            ),
            url="https://slack.com/api/users.info",
        )
    except Exception:  # noqa: BLE001
        cache[user_id] = {}
        return None

    user_payload = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    profile = user_payload.get("profile") if isinstance(user_payload.get("profile"), dict) else {}
    cached_profile = {
        "id": user_id,
        "name": user_payload.get("real_name") or user_payload.get("name"),
        "display_name": profile.get("display_name") or profile.get("real_name"),
        "email": profile.get("email"),
    }
    cache[user_id] = cached_profile
    return cached_profile


def _ensure_slack_ok(payload: dict[str, Any], url: str) -> dict[str, Any]:
    if payload.get("ok") is False:
        error_code = payload.get("error") or "unknown_error"
        raise ValueError(f"Slack API error from {url}: {error_code}")
    return payload


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


def _inline_index_items(db, item_ids: list[uuid.UUID], user_id: uuid.UUID) -> None:
    """Chunk and embed upserted items within the current DB session so item_chunks
    rows are populated synchronously on every sync, even without Celery workers."""
    if not item_ids:
        return

    items = db.execute(
        select(Item).where(Item.id.in_(item_ids), Item.user_id == user_id)
    ).scalars().all()

    for item in items:
        try:
            result = index_item_chunks(db=db, item=item)
            metadata = dict(item.metadata_json or {})
            metadata["embedding_status"] = "completed"
            metadata["embedded_at"] = datetime.now(UTC).isoformat()
            metadata["chunk_count"] = result.chunk_count
            item.metadata_json = metadata
        except Exception:
            logger.exception("Inline indexing failed for item %s", item.id)


def _enqueue_indexing_tasks(item_ids: list[uuid.UUID], user_id: uuid.UUID, source: str) -> None:
    if not item_ids:
        return

    try:
        from workers.celery_app import celery_app

        for item_id in item_ids:
            celery_app.send_task(
                "workers.file_watcher_worker.watch_file_changes",
                args=[str(item_id), str(user_id), source],
            )
    except Exception:
        logger.exception("Unable to enqueue post-ingest indexing tasks")


def _upsert_items(db, rows: list[dict[str, Any]]) -> list[uuid.UUID]:
    if not rows:
        return []

    stmt = insert(Item).values(rows)
    metadata_without_runtime = _metadata_without_runtime_fields
    change_predicates = [
        Item.type.is_distinct_from(stmt.excluded.type),
        Item.title.is_distinct_from(stmt.excluded.title),
        Item.sender_name.is_distinct_from(stmt.excluded.sender_name),
        Item.sender_email.is_distinct_from(stmt.excluded.sender_email),
        Item.content.is_distinct_from(stmt.excluded.content),
        Item.summary.is_distinct_from(stmt.excluded.summary),
        Item.item_date.is_distinct_from(stmt.excluded.item_date),
        Item.file_path.is_distinct_from(stmt.excluded.file_path),
        metadata_without_runtime(Item.metadata_json).is_distinct_from(
            metadata_without_runtime(stmt.excluded.metadata)
        ),
    ]
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
        where=or_(*change_predicates),
    ).returning(Item.id)

    result = db.execute(upsert_stmt)
    return list(result.scalars().all())


def _metadata_without_runtime_fields(expr):
    """Ignore ingestion/runtime keys that should not trigger re-embedding."""
    return expr.op("-")("cursor").op("-")("embedding_status").op("-")("embedded_at").op("-")("chunk_count")


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
