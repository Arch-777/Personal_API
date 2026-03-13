from __future__ import annotations

import base64
import threading
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.config import get_settings
from api.core.db import SessionLocal, get_db
from api.core.security import create_access_token, decode_access_token
from api.models.connector import Connector
from api.models.user import User
from api.schemas.connector import ConnectorResponse, ConnectorSyncResponse
from workers.celery_app import celery_app
from workers.connector_sync import run_connector_sync


router = APIRouter(prefix="/connectors", tags=["connectors"])

PLATFORM_TO_TASK = {
    "gmail": "workers.google_worker.sync_gmail",
    "drive": "workers.google_worker.sync_drive",
    "gcal": "workers.google_worker.sync_gcal",
    "notion": "workers.notion_worker.sync_notion",
    "spotify": "workers.spotify_worker.sync_spotify",
    "slack": "workers.slack_worker.sync_slack",
}

GOOGLE_PLATFORM_SCOPES: dict[str, list[str]] = {
    "gmail": [
        "openid",
        "email",
        "https://www.googleapis.com/auth/gmail.readonly",
    ],
    "drive": [
        "openid",
        "email",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
    "gcal": [
        "openid",
        "email",
        "https://www.googleapis.com/auth/calendar.readonly",
    ],
}

GOOGLE_CONNECTOR_PLATFORMS = ("gmail", "drive", "gcal")


def _ensure_google_connector_row(
    db: Session,
    user_id: uuid.UUID,
    platform: str,
    access_token: str,
    refresh_token: str | None,
    token_expires_at: datetime,
    platform_email: str | None,
    google_scope: str | None,
) -> Connector:
    existing = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform == platform,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.encrypted_access_token = access_token
        if refresh_token:
            existing.encrypted_refresh_token = refresh_token
        existing.token_expires_at = token_expires_at
        if platform_email:
            existing.platform_email = platform_email
        existing.status = "connected"
        existing.error_message = None
        metadata = existing.metadata_json if isinstance(existing.metadata_json, dict) else {}
        metadata["google_scopes"] = google_scope
        existing.metadata_json = metadata
        return existing

    connector = Connector(
        id=uuid.uuid4(),
        user_id=user_id,
        platform=platform,
        platform_email=platform_email,
        encrypted_access_token=access_token,
        encrypted_refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        status="connected",
        metadata_json={"google_scopes": google_scope},
    )
    db.add(connector)
    return connector


def _clone_missing_google_connector_from_existing(
    db: Session,
    user_id: uuid.UUID,
    target_platform: str,
) -> Connector | None:
    source = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform.in_(GOOGLE_CONNECTOR_PLATFORMS),
        )
    ).scalars().first()
    if source is None:
        return None

    metadata = source.metadata_json if isinstance(source.metadata_json, dict) else {}
    cloned_metadata = dict(metadata)
    cloned_metadata["google_connector_cloned_from"] = source.platform

    connector = Connector(
        id=uuid.uuid4(),
        user_id=user_id,
        platform=target_platform,
        platform_email=source.platform_email,
        encrypted_access_token=source.encrypted_access_token,
        encrypted_refresh_token=source.encrypted_refresh_token,
        token_expires_at=source.token_expires_at,
        status="connected",
        error_message=None,
        metadata_json=cloned_metadata,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


@router.get("/google/connect")
def google_connect(
    platform: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    settings = get_settings()
    normalized_platform = platform.strip().lower()
    scopes = GOOGLE_PLATFORM_SCOPES.get(normalized_platform)
    if scopes is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported Google connector platform")
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google connector is not configured")

    state = create_access_token(f"{current_user.id}|{normalized_platform}", expires_minutes=10)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"}


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google connector is not configured")

    try:
        payload = decode_access_token(state)
        state_subject = payload["sub"]
        user_part, platform_part = state_subject.split("|", maxsplit=1)
        user_id = uuid.UUID(user_part)
        normalized_platform = platform_part.strip().lower()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter") from exc

    if normalized_platform not in GOOGLE_PLATFORM_SCOPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported Google connector platform")

    try:
        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Google auth code for tokens") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token response from Google")

    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in", 3600))
    token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    platform_email: str | None = None
    try:
        with httpx.Client(timeout=10.0) as client:
            profile_resp = client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_resp.status_code == 200:
                platform_email = profile_resp.json().get("email")
    except Exception:  # noqa: BLE001
        pass

    # Ensure the requested Google connector exists and proactively create sibling
    # Google connector rows to avoid "Connector not found" for drive/gcal/gmail.
    token_scope = token_data.get("scope") if isinstance(token_data.get("scope"), str) else None
    _ensure_google_connector_row(
        db=db,
        user_id=user_id,
        platform=normalized_platform,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        platform_email=platform_email,
        google_scope=token_scope,
    )

    for platform_name in GOOGLE_CONNECTOR_PLATFORMS:
        _ensure_google_connector_row(
            db=db,
            user_id=user_id,
            platform=platform_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            platform_email=platform_email,
            google_scope=token_scope,
        )
    db.commit()

    return {"status": "connected", "platform": normalized_platform}


# ---------------------------------------------------------------------------
# Notion connector endpoints
# ---------------------------------------------------------------------------

@router.get("/notion/connect")
def notion_connect(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Notion OAuth authorisation URL."""
    settings = get_settings()
    if not settings.notion_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Notion integration is not configured")

    state = create_access_token(str(current_user.id), expires_minutes=10)
    params = {
        "client_id": settings.notion_client_id,
        "redirect_uri": settings.notion_redirect_uri,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    return {"url": f"https://api.notion.com/v1/oauth/authorize?{urllib.parse.urlencode(params)}"}


@router.get("/notion/callback")
def notion_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Exchange Notion OAuth code for a workspace access token and save the connector row."""
    settings = get_settings()
    if not settings.notion_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Notion integration is not configured")

    try:
        payload = decode_access_token(state)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter") from exc

    credentials = base64.b64encode(
        f"{settings.notion_client_id}:{settings.notion_client_secret}".encode()
    ).decode()

    try:
        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://api.notion.com/v1/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.notion_redirect_uri,
                },
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                    "Notion-Version": "2022-06-28",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Notion auth code for tokens") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token response from Notion")

    workspace_name = token_data.get("workspace_name", "")
    workspace_id = token_data.get("workspace_id", "")
    bot_id = token_data.get("bot_id", "")
    owner_info = token_data.get("owner", {})
    platform_email: str | None = None
    if isinstance(owner_info, dict):
        person = owner_info.get("person", {})
        if isinstance(person, dict):
            platform_email = person.get("email")

    _upsert_notion_connector(
        db=db,
        user_id=user_id,
        access_token=access_token,
        platform_email=platform_email,
        metadata={"workspace_name": workspace_name, "workspace_id": workspace_id, "bot_id": bot_id},
    )
    return {"status": "connected", "platform": "notion", "workspace": workspace_name}


class NotionTokenRequest(object):
    """Pydantic-free DTO — use as body schema via Annotated dict in route."""


from pydantic import BaseModel  # noqa: E402  (needed here for inline model)


class _NotionTokenBody(BaseModel):
    access_token: str


@router.post("/notion/token")
def notion_quick_token(
    body: _NotionTokenBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Quick-connect for hackathon / dev: register a Notion internal integration token directly.

    Obtain your token from https://www.notion.so/my-integrations  (starts with `ntn_` or `secret_`).
    """
    access_token = body.access_token.strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="access_token must not be empty")

    # Verify the token against Notion by fetching /v1/users/me
    try:
        with httpx.Client(timeout=10.0) as client:
            me_resp = client.get(
                "https://api.notion.com/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}", "Notion-Version": "2022-06-28"},
            )
            me_resp.raise_for_status()
            me_data = me_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Notion token or Notion API error") from exc

    platform_email: str | None = None
    person = me_data.get("person", {})
    if isinstance(person, dict):
        platform_email = person.get("email")
    bot = me_data.get("bot", {})
    workspace_name: str = ""
    if isinstance(bot, dict):
        workspace = bot.get("workspace_name", "")
        if isinstance(workspace, str):
            workspace_name = workspace

    _upsert_notion_connector(
        db=db,
        user_id=current_user.id,
        access_token=access_token,
        platform_email=platform_email,
        metadata={"workspace_name": workspace_name, "bot_id": me_data.get("id", "")},
    )
    return {"status": "connected", "platform": "notion", "workspace": workspace_name}


def _upsert_notion_connector(
    db: Session,
    user_id: uuid.UUID,
    access_token: str,
    platform_email: str | None,
    metadata: dict,
) -> None:
    existing = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform == "notion",
        )
    ).scalar_one_or_none()

    if existing:
        existing.encrypted_access_token = access_token
        existing.encrypted_refresh_token = None  # Notion OAuth has no refresh token
        existing.token_expires_at = None
        if platform_email:
            existing.platform_email = platform_email
        existing.status = "connected"
        existing.error_message = None
        existing.metadata_json = metadata
        db.commit()
    else:
        connector = Connector(
            id=uuid.uuid4(),
            user_id=user_id,
            platform="notion",
            platform_email=platform_email,
            encrypted_access_token=access_token,
            encrypted_refresh_token=None,
            token_expires_at=None,
            status="connected",
            metadata_json=metadata,
        )
        db.add(connector)
        db.commit()


@router.get("/spotify/connect")
def spotify_connect(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Spotify authorisation URL the frontend should redirect the user to."""
    settings = get_settings()
    if not settings.spotify_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Spotify integration is not configured")

    # Embed user_id in state as a short-lived JWT so the callback can identify the user without a session.
    state = create_access_token(str(current_user.id), expires_minutes=10)

    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": "user-read-recently-played user-top-read user-library-read user-read-currently-playing",
        "state": state,
        "show_dialog": "false",
    }
    query_string = urllib.parse.urlencode(params)
    return {"url": f"https://accounts.spotify.com/authorize?{query_string}"}


@router.get("/spotify/callback")
def spotify_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Exchange Spotify auth code for tokens and save/update the connector row."""
    settings = get_settings()
    if not settings.spotify_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Spotify integration is not configured")

    try:
        payload = decode_access_token(state)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter") from exc

    credentials = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()

    try:
        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.spotify_redirect_uri,
                },
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Spotify auth code for tokens") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token response from Spotify")

    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in", 3600))
    token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    # Fetch the Spotify user profile to store their email.
    platform_email: str | None = None
    try:
        with httpx.Client(timeout=10.0) as client:
            me_resp = client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if me_resp.status_code == 200:
                platform_email = me_resp.json().get("email")
    except Exception:  # noqa: BLE001
        pass

    existing = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform == "spotify",
        )
    ).scalar_one_or_none()

    if existing:
        existing.encrypted_access_token = access_token
        if refresh_token:
            existing.encrypted_refresh_token = refresh_token
        existing.token_expires_at = token_expires_at
        if platform_email:
            existing.platform_email = platform_email
        existing.status = "connected"
        existing.error_message = None
        db.commit()
    else:
        connector = Connector(
            id=uuid.uuid4(),
            user_id=user_id,
            platform="spotify",
            platform_email=platform_email,
            encrypted_access_token=access_token,
            encrypted_refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            status="connected",
            metadata_json={},
        )
        db.add(connector)
        db.commit()

    return {"status": "connected", "platform": "spotify"}


@router.get("/slack/connect")
def slack_connect(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Slack authorisation URL the client should redirect the user to."""
    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Slack integration is not configured")

    state = create_access_token(str(current_user.id), expires_minutes=10)
    params = {
        "client_id": settings.slack_client_id,
        "redirect_uri": settings.slack_redirect_uri,
        "scope": "channels:history,channels:read,groups:history,groups:read,im:history,im:read,mpim:history,mpim:read,users:read,users:read.email",
        "state": state,
        "user_scope": "channels:history,groups:history,im:history,mpim:history,channels:read,groups:read,im:read,mpim:read,users:read,users:read.email",
    }
    return {"url": f"https://slack.com/oauth/v2/authorize?{urllib.parse.urlencode(params)}"}


@router.get("/slack/callback")
def slack_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Exchange Slack auth code for tokens and save/update the connector row."""
    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Slack integration is not configured")

    try:
        payload = decode_access_token(state)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter") from exc

    try:
        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.slack_client_id,
                    "client_secret": settings.slack_client_secret,
                    "code": code,
                    "redirect_uri": settings.slack_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Slack auth code for tokens") from exc

    if not isinstance(token_data, dict) or not token_data.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token response from Slack")

    authed_user = token_data.get("authed_user") if isinstance(token_data.get("authed_user"), dict) else {}
    access_token = authed_user.get("access_token") or token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token response from Slack")

    platform_email: str | None = None
    slack_user_id = authed_user.get("id") if isinstance(authed_user.get("id"), str) else None
    if slack_user_id:
        try:
            with httpx.Client(timeout=10.0) as client:
                me_resp = client.get(
                    "https://slack.com/api/users.info",
                    params={"user": slack_user_id},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                me_resp.raise_for_status()
                me_data = me_resp.json()
            if isinstance(me_data, dict) and me_data.get("ok"):
                user_payload = me_data.get("user") if isinstance(me_data.get("user"), dict) else {}
                profile_payload = user_payload.get("profile") if isinstance(user_payload.get("profile"), dict) else {}
                platform_email = profile_payload.get("email") if isinstance(profile_payload.get("email"), str) else None
        except Exception:  # noqa: BLE001
            pass

    team_payload = token_data.get("team") if isinstance(token_data.get("team"), dict) else {}
    metadata = {
        "team_id": team_payload.get("id"),
        "team_name": team_payload.get("name"),
        "scope": token_data.get("scope"),
        "slack_user_id": slack_user_id,
    }

    existing = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform == "slack",
        )
    ).scalar_one_or_none()

    if existing:
        existing.encrypted_access_token = access_token
        existing.encrypted_refresh_token = None
        existing.token_expires_at = None
        if platform_email:
            existing.platform_email = platform_email
        existing.status = "connected"
        existing.error_message = None
        existing.metadata_json = metadata
        db.commit()
    else:
        connector = Connector(
            id=uuid.uuid4(),
            user_id=user_id,
            platform="slack",
            platform_email=platform_email,
            encrypted_access_token=access_token,
            encrypted_refresh_token=None,
            token_expires_at=None,
            status="connected",
            metadata_json=metadata,
        )
        db.add(connector)
        db.commit()

    return {"status": "connected", "platform": "slack"}


@router.get("/", response_model=list[ConnectorResponse])
def list_connectors(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ConnectorResponse]:
    rows = db.execute(
        select(Connector)
        .where(Connector.user_id == current_user.id)
        .order_by(Connector.platform.asc(), Connector.created_at.desc())
    ).scalars().all()
    return [ConnectorResponse.model_validate(row) for row in rows]


@router.post("/{platform}/sync", response_model=ConnectorSyncResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_connector(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorSyncResponse:
    settings = get_settings()
    normalized_platform = platform.strip().lower()
    task_name = PLATFORM_TO_TASK.get(normalized_platform)
    if task_name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported connector platform")

    connector = db.execute(
        select(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform == normalized_platform,
        )
    ).scalar_one_or_none()
    if connector is None:
        if normalized_platform in GOOGLE_CONNECTOR_PLATFORMS:
            connector = _clone_missing_google_connector_from_existing(
                db=db,
                user_id=current_user.id,
                target_platform=normalized_platform,
            )
        if connector is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    # Clear stale errors, but only workers should mark a connector as actively syncing.
    connector.error_message = None
    db.commit()

    try:
        celery_app.send_task(
            task_name,
            args=[str(connector.id), str(current_user.id), connector.sync_cursor],
        )
    except Exception as exc:  # noqa: BLE001
        # Development-only fallback: run inline only when explicitly enabled.
        if settings.debug and settings.enable_inline_sync_fallback:
            connector_id = str(connector.id)
            user_id = str(current_user.id)
            cursor = connector.sync_cursor

            def _run_inline_sync() -> None:
                try:
                    run_connector_sync(
                        platform=normalized_platform,
                        connector_id=connector_id,
                        user_id=user_id,
                        cursor=cursor,
                    )
                except Exception as inline_exc:  # noqa: BLE001
                    with SessionLocal() as inline_db:
                        failed_connector = inline_db.execute(
                            select(Connector).where(
                                Connector.id == uuid.UUID(connector_id),
                                Connector.user_id == uuid.UUID(user_id),
                                Connector.platform == normalized_platform,
                            )
                        ).scalar_one_or_none()
                        if failed_connector is not None:
                            failed_connector.status = "error"
                            failed_connector.error_message = f"Inline sync failed: {inline_exc}"
                            inline_db.commit()

            threading.Thread(target=_run_inline_sync, daemon=True).start()
            return ConnectorSyncResponse(status="sync_queued_inline", platform=normalized_platform)

        connector.status = "error"
        connector.error_message = f"Queue unavailable: {exc}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sync queue unavailable. Start Redis/Celery.",
        ) from exc

    return ConnectorSyncResponse(status="sync_queued", platform=normalized_platform)


@router.get("/{platform}", response_model=ConnectorResponse)
def get_connector(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorResponse:
    normalized_platform = platform.strip().lower()
    connector = db.execute(
        select(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform == normalized_platform,
        )
    ).scalar_one_or_none()
    if connector is None:
        if normalized_platform in GOOGLE_CONNECTOR_PLATFORMS:
            connector = _clone_missing_google_connector_from_existing(
                db=db,
                user_id=current_user.id,
                target_platform=normalized_platform,
            )
        if connector is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    return ConnectorResponse.model_validate(connector)


@router.post("/{platform}/bootstrap", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_connector(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorResponse:
    normalized_platform = platform.strip().lower()
    if normalized_platform not in PLATFORM_TO_TASK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported connector platform")

    existing = db.execute(
        select(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform == normalized_platform,
        )
    ).scalar_one_or_none()
    if existing:
        return ConnectorResponse.model_validate(existing)

    connector = Connector(
        id=uuid.uuid4(),
        user_id=current_user.id,
        platform=normalized_platform,
        encrypted_access_token=f"dev-token-{normalized_platform}",
        encrypted_refresh_token=f"dev-refresh-{normalized_platform}",
        status="connected",
        metadata_json={"bootstrap": True},
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return ConnectorResponse.model_validate(connector)
