from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.config import get_settings
from api.core.db import SessionLocal, get_db
from api.core.http_client import get_http_client
from api.core.security import create_access_token, decode_access_token
from api.models.connector import Connector
from api.models.item import Item
from api.models.user import User
from api.schemas.connector import (
    ConnectorAutoSyncResponse,
    ConnectorAutoSyncUpdateRequest,
    ConnectorDisconnectResponse,
    ConnectorResponse,
    ConnectorSyncResponse,
)
from workers.celery_app import celery_app
from workers.connector_sync import run_connector_sync


router = APIRouter(prefix="/connectors", tags=["connectors"])

PLATFORM_TO_TASK = {
    "gmail": "workers.google_worker.sync_gmail",
    "drive": "workers.google_worker.sync_drive",
    "gcal": "workers.google_worker.sync_gcal",
    "github": "workers.github_worker.sync_github",
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
GITHUB_CONNECT_SCOPES = "read:user user:email repo"
GITHUB_WEBHOOK_EVENTS = {"push", "pull_request", "issues", "repository", "release", "create", "delete"}


def _parse_github_token_response(token_response: object) -> dict[str, object]:
    token_data: dict[str, object] = {}

    def _set_if_missing(key: str, value: object) -> None:
        normalized_key = key.strip()
        if not normalized_key or normalized_key in token_data:
            return
        token_data[normalized_key] = value

    raw_text = ""
    response_text = getattr(token_response, "text", None)
    if isinstance(response_text, str):
        raw_text = response_text.strip()

    parsed_json: object = None
    json_loader = getattr(token_response, "json", None)
    if callable(json_loader):
        try:
            parsed_json = json_loader()
        except ValueError:
            parsed_json = None

    if isinstance(parsed_json, dict):
        for key, value in parsed_json.items():
            if isinstance(key, str):
                _set_if_missing(key, value)
    elif isinstance(parsed_json, str) and parsed_json.strip():
        raw_text = parsed_json.strip()

    if raw_text and "=" in raw_text:
        for key, value in urllib.parse.parse_qsl(raw_text, keep_blank_values=True):
            _set_if_missing(key, value)

    return token_data


def _build_github_token_exchange_error_detail(token_data: dict[str, object]) -> str | None:
    github_error = token_data.get("error")
    github_error_description = token_data.get("error_description")
    github_message = token_data.get("message")

    if isinstance(github_error, str) and github_error.strip():
        detail = f"GitHub token exchange failed: {github_error.strip()}"
        if isinstance(github_error_description, str) and github_error_description.strip():
            detail += f" ({github_error_description.strip()})"
        return detail

    if isinstance(github_error_description, str) and github_error_description.strip():
        return f"GitHub token exchange failed: {github_error_description.strip()}"

    if isinstance(github_message, str) and github_message.strip():
        return f"GitHub token exchange failed: {github_message.strip()}"

    github_errors = token_data.get("errors")
    if isinstance(github_errors, list) and github_errors:
        first_error = github_errors[0]
        if isinstance(first_error, str) and first_error.strip():
            return f"GitHub token exchange failed: {first_error.strip()}"
        if isinstance(first_error, dict):
            first_message = first_error.get("message")
            if isinstance(first_message, str) and first_message.strip():
                return f"GitHub token exchange failed: {first_message.strip()}"

    return None


def _build_frontend_integrations_callback_url(platform: str, ok: bool, message: str | None = None) -> str:
    settings = get_settings()
    base = settings.frontend_app_url.rstrip("/")

    normalized_message: str | None = None
    if isinstance(message, str):
        candidate = " ".join(message.replace("\r", " ").replace("\n", " ").split()).strip()
        if candidate:
            # Keep query strings short and avoid leaking verbose backend internals to browser URLs.
            normalized_message = candidate[:180]

    query = {
        "integration": platform,
        "status": "success" if ok else "error",
    }
    if normalized_message:
        query["message"] = normalized_message
    return f"{base}/dashboard/integrations?{urllib.parse.urlencode(query)}"


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


def _upsert_github_connector(
    db: Session,
    user_id: uuid.UUID,
    access_token: str,
    platform_email: str | None,
    metadata: dict,
) -> None:
    existing = db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.platform == "github",
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
        return

    connector = Connector(
        id=uuid.uuid4(),
        user_id=user_id,
        platform="github",
        platform_email=platform_email,
        encrypted_access_token=access_token,
        encrypted_refresh_token=None,
        token_expires_at=None,
        status="connected",
        metadata_json=metadata,
    )
    db.add(connector)
    db.commit()


def _is_valid_github_webhook_signature(secret: str, payload: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _github_connector_matches_owner(connector: Connector, owner_login: str) -> bool:
    metadata = connector.metadata_json if isinstance(connector.metadata_json, dict) else {}
    owner_candidates: set[str] = set()

    login = metadata.get("github_login")
    if isinstance(login, str) and login.strip():
        owner_candidates.add(login.strip().lower())

    orgs = metadata.get("github_org_logins")
    if isinstance(orgs, list):
        for org in orgs:
            if isinstance(org, str) and org.strip():
                owner_candidates.add(org.strip().lower())

    return owner_login.strip().lower() in owner_candidates


def _find_matching_github_connectors(db: Session, owner_login: str) -> list[Connector]:
    rows = db.execute(
        select(Connector).where(Connector.platform == "github")
    ).scalars().all()

    return [connector for connector in rows if _github_connector_matches_owner(connector, owner_login)]


@router.get("/github/connect")
def github_connect(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub integration is not configured")

    state = create_access_token(f"{current_user.id}|github", expires_minutes=10)
    params = {
        "client_id": settings.github_client_id,
        "scope": GITHUB_CONNECT_SCOPES,
        "state": state,
    }
    if settings.github_redirect_uri:
        params["redirect_uri"] = settings.github_redirect_uri
    return {"url": f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"}


@router.get("/github/callback", response_model=None)
def github_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    redirect_to_frontend: bool = True,
) -> RedirectResponse | dict[str, str]:
    settings = get_settings()

    def _frontend_redirect(ok: bool, message: str) -> RedirectResponse:
        redirect_url = _build_frontend_integrations_callback_url(
            platform="github",
            ok=ok,
            message=message,
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    if not settings.github_client_id or not settings.github_client_secret:
        detail = "GitHub integration is not configured"
        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message=detail)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    code = code.strip()
    state = state.strip()

    if not code:
        detail = "Missing GitHub OAuth code"
        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    if not state:
        detail = "Missing OAuth state parameter"
        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    try:
        payload = decode_access_token(state)
        state_subject = str(payload["sub"])
        user_part, platform_part = state_subject.split("|", maxsplit=1)
        user_id = uuid.UUID(user_part)
        if platform_part.strip().lower() != "github":
            raise ValueError("Invalid connector in OAuth state")
    except Exception as exc:  # noqa: BLE001
        detail = "Invalid or expired state parameter"
        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    try:
        token_request_payload = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
        }
        if settings.github_redirect_uri:
            token_request_payload["redirect_uri"] = settings.github_redirect_uri

        client = get_http_client(15.0)
        token_resp = client.post(
            "https://github.com/login/oauth/access_token",
            data=token_request_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        token_resp.raise_for_status()
        token_data = _parse_github_token_response(token_resp)
    except httpx.HTTPError as exc:
        detail = "Failed to exchange GitHub auth code for tokens"
        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    access_token_candidates = (
        token_data.get("access_token"),
        token_data.get("accessToken"),
        token_data.get("token"),
    )
    access_token = next(
        (
            token_value.strip()
            for token_value in access_token_candidates
            if isinstance(token_value, str) and token_value.strip()
        ),
        None,
    )
    if access_token is None:
        detail = _build_github_token_exchange_error_detail(token_data)
        if detail is not None:
            if redirect_to_frontend:
                return _frontend_redirect(ok=False, message=detail)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        response_status = getattr(token_resp, "status_code", "unknown")
        response_content_type = token_resp.headers.get("content-type", "unknown")
        response_text = getattr(token_resp, "text", "")
        preview = ""
        if isinstance(response_text, str) and response_text.strip():
            preview = response_text.strip().replace("\r", " ").replace("\n", " ")[:220]

        fallback_detail = (
            "Invalid token response from GitHub [oauth-parser-v2]"
            f" (status={response_status}, content_type={response_content_type}, token_fields={sorted(token_data.keys())})"
        )
        if preview:
            fallback_detail += f": {preview}"

        if redirect_to_frontend:
            return _frontend_redirect(ok=False, message="GitHub OAuth callback returned an invalid token response")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=fallback_detail)

    github_login: str | None = None
    github_name: str | None = None
    platform_email: str | None = None
    github_org_logins: list[str] = []

    try:
        client = get_http_client(15.0)
        profile_resp = client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        profile_resp.raise_for_status()
        profile_data = profile_resp.json()

        github_login = profile_data.get("login") if isinstance(profile_data.get("login"), str) else None
        github_name = profile_data.get("name") if isinstance(profile_data.get("name"), str) else None
        profile_email = profile_data.get("email") if isinstance(profile_data.get("email"), str) else None
        if profile_email:
            platform_email = profile_email

        emails_resp = client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if emails_resp.status_code == 200:
            emails_data = emails_resp.json()
            if isinstance(emails_data, list):
                primary_verified = next(
                    (
                        item.get("email")
                        for item in emails_data
                        if isinstance(item, dict)
                        and item.get("primary") is True
                        and item.get("verified") is True
                        and isinstance(item.get("email"), str)
                    ),
                    None,
                )
                if isinstance(primary_verified, str) and primary_verified.strip():
                    platform_email = primary_verified

        orgs_resp = client.get(
            "https://api.github.com/user/orgs",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if orgs_resp.status_code == 200:
            orgs_data = orgs_resp.json()
            if isinstance(orgs_data, list):
                github_org_logins = [
                    org["login"].strip()
                    for org in orgs_data
                    if isinstance(org, dict)
                    and isinstance(org.get("login"), str)
                    and org["login"].strip()
                ]
    except Exception:  # noqa: BLE001
        # Profile enrichment is best-effort; connection still succeeds with access token.
        pass

    metadata = {
        "github_login": github_login,
        "github_name": github_name,
        "github_org_logins": github_org_logins,
        "scopes": token_data.get("scope"),
        "token_type": token_data.get("token_type"),
    }
    _upsert_github_connector(
        db=db,
        user_id=user_id,
        access_token=access_token,
        platform_email=platform_email,
        metadata=metadata,
    )

    success_message = "Connected github"
    if redirect_to_frontend:
        return _frontend_redirect(ok=True, message=success_message)

    return {
        "status": "connected",
        "platform": "github",
        "github_login": github_login or "",
    }


@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.github_webhook_secret.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub webhook is not configured")

    signature_header = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event", "").strip().lower()
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    payload_bytes = await request.body()
    if not _is_valid_github_webhook_signature(settings.github_webhook_secret, payload_bytes, signature_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload")

    if event_type == "ping":
        return {
            "status": "ok",
            "event": "ping",
            "delivery_id": delivery_id,
        }

    if event_type not in GITHUB_WEBHOOK_EVENTS:
        return {
            "status": "ignored",
            "event": event_type,
            "delivery_id": delivery_id,
            "reason": "unsupported_event",
        }

    repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    owner_payload = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
    owner_login = owner_payload.get("login") if isinstance(owner_payload.get("login"), str) else None
    repository_name = repository.get("full_name") if isinstance(repository.get("full_name"), str) else ""

    if not owner_login and repository_name and "/" in repository_name:
        owner_login = repository_name.split("/", 1)[0]

    if not owner_login:
        return {
            "status": "ignored",
            "event": event_type,
            "delivery_id": delivery_id,
            "reason": "missing_repository_owner",
        }

    matched_connectors = _find_matching_github_connectors(db, owner_login)
    if not matched_connectors:
        return {
            "status": "ignored",
            "event": event_type,
            "delivery_id": delivery_id,
            "owner_login": owner_login,
            "reason": "no_matching_connector",
        }

    queued_jobs = 0
    inline_jobs = 0
    for connector in matched_connectors:
        try:
            celery_app.send_task(
                PLATFORM_TO_TASK["github"],
                args=[str(connector.id), str(connector.user_id), connector.sync_cursor],
            )
            queued_jobs += 1
        except Exception as exc:  # noqa: BLE001
            if settings.debug and settings.enable_inline_sync_fallback:
                connector_id = str(connector.id)
                user_id = str(connector.user_id)
                cursor = connector.sync_cursor

                def _run_inline_sync() -> None:
                    try:
                        run_connector_sync(
                            platform="github",
                            connector_id=connector_id,
                            user_id=user_id,
                            cursor=cursor,
                        )
                    except Exception:
                        pass

                threading.Thread(target=_run_inline_sync, daemon=True).start()
                inline_jobs += 1
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Webhook accepted but queue unavailable: {exc}",
                ) from exc

    return {
        "status": "accepted",
        "event": event_type,
        "delivery_id": delivery_id,
        "owner_login": owner_login,
        "repository": repository_name,
        "matched_connectors": len(matched_connectors),
        "queued_sync_jobs": queued_jobs,
        "inline_sync_jobs": inline_jobs,
    }


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
) -> RedirectResponse:
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
        client = get_http_client(15.0)
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
        client = get_http_client(10.0)
        profile_resp = client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code == 200:
            platform_email = profile_resp.json().get("email")
    except Exception:  # noqa: BLE001
        pass

    # Upsert each Google platform once to avoid duplicate pending inserts in the
    # same transaction and to keep sibling connector rows in sync.
    token_scope = token_data.get("scope") if isinstance(token_data.get("scope"), str) else None
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

    redirect_url = _build_frontend_integrations_callback_url(
        platform=normalized_platform,
        ok=True,
        message=f"Connected {normalized_platform}",
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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
) -> RedirectResponse:
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
        client = get_http_client(15.0)
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
    redirect_url = _build_frontend_integrations_callback_url(
        platform="notion",
        ok=True,
        message=f"Connected notion workspace {workspace_name}" if workspace_name else "Connected notion",
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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
        client = get_http_client(10.0)
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
) -> RedirectResponse:
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
        client = get_http_client(15.0)
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
        client = get_http_client(10.0)
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

    redirect_url = _build_frontend_integrations_callback_url(
        platform="spotify",
        ok=True,
        message="Connected spotify",
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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
) -> RedirectResponse:
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
        client = get_http_client(15.0)
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
            client = get_http_client(10.0)
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

    redirect_url = _build_frontend_integrations_callback_url(
        platform="slack",
        ok=True,
        message="Connected slack",
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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


@router.delete(
    "/{platform}",
    response_model=ConnectorDisconnectResponse,
    summary="Disconnect an integration",
)
def disconnect_connector(
    platform: str,
    delete_data: bool = False,
    cascade_google: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorDisconnectResponse:
    """Remove a connector and, optionally, all synced data for that platform.

    - **delete_data** (default ``false``): when ``true``, also deletes all ``items``
      (and their ``item_chunks`` via cascade) that were synced from this platform.
    - **cascade_google** (default ``true``): when ``true`` and the platform is one of
      ``gmail``, ``drive``, or ``gcal``, all three Google connectors are removed
      together because they share a single OAuth token.
    """
    normalized_platform = platform.strip().lower()
    if normalized_platform not in PLATFORM_TO_TASK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported connector platform '{normalized_platform}'",
        )

    # Build the list of connector platforms to remove.
    platforms_to_remove: list[str]
    if cascade_google and normalized_platform in GOOGLE_CONNECTOR_PLATFORMS:
        platforms_to_remove = list(GOOGLE_CONNECTOR_PLATFORMS)
    else:
        platforms_to_remove = [normalized_platform]

    # Verify at least one connector row actually exists for this user.
    connectors = db.execute(
        select(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform.in_(platforms_to_remove),
        )
    ).scalars().all()

    if not connectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected integration found for the requested platform",
        )

    actually_removed = [c.platform for c in connectors]

    # Optionally wipe all synced items from the affected platforms.
    items_deleted = 0
    if delete_data:
        for source_platform in actually_removed:
            result = db.execute(
                delete(Item).where(
                    Item.user_id == current_user.id,
                    Item.source == source_platform,
                )
            )
            items_deleted += result.rowcount  # type: ignore[union-attr]

    # Delete the connector rows themselves.
    db.execute(
        delete(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform.in_(actually_removed),
        )
    )
    db.commit()

    return ConnectorDisconnectResponse(
        disconnected=sorted(actually_removed),
        items_deleted=items_deleted,
    )


@router.patch(
    "/{platform}/auto-sync",
    response_model=ConnectorAutoSyncResponse,
    summary="Enable or disable automatic periodic sync for an integration",
)
def set_connector_auto_sync(
    platform: str,
    body: ConnectorAutoSyncUpdateRequest,
    cascade_google: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorAutoSyncResponse:
    normalized_platform = platform.strip().lower()
    if normalized_platform not in PLATFORM_TO_TASK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported connector platform '{normalized_platform}'",
        )

    if cascade_google and normalized_platform in GOOGLE_CONNECTOR_PLATFORMS:
        target_platforms = list(GOOGLE_CONNECTOR_PLATFORMS)
    else:
        target_platforms = [normalized_platform]

    connectors = db.execute(
        select(Connector).where(
            Connector.user_id == current_user.id,
            Connector.platform.in_(target_platforms),
        )
    ).scalars().all()

    if not connectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected integration found for the requested platform",
        )

    for connector in connectors:
        metadata = connector.metadata_json if isinstance(connector.metadata_json, dict) else {}
        metadata["auto_sync_enabled"] = body.enabled
        connector.metadata_json = metadata

    db.commit()

    return ConnectorAutoSyncResponse(
        platforms=sorted([connector.platform for connector in connectors]),
        auto_sync_enabled=body.enabled,
    )


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
