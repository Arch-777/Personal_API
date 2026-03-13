"""WebSocket router — real-time push notifications for sync events.

Clients connect with:
    ws://<host>/ws?token=<JWT>

The server fan-outs typed event envelopes to all authenticated connections
belonging to a user.  Other parts of the codebase (Celery tasks, router
endpoints) publish events by calling ``broadcast_to_user``.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from api.core.db import SessionLocal
from api.core.security import decode_access_token
from api.models.user import User
from sqlalchemy import select


logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# ---------------------------------------------------------------------------
# In-process connection registry
# user_id (str) → set of active WebSocket connections
# ---------------------------------------------------------------------------
_connections: dict[str, set[WebSocket]] = {}
_registry_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Public helper — fire-and-forget from sync workers / routers
# ---------------------------------------------------------------------------

async def broadcast_to_user(user_id: str, event: str, data: dict[str, Any]) -> None:
    """Send a typed event envelope to every open connection for *user_id*."""
    envelope = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "data": data,
    }
    async with _registry_lock:
        sockets = list(_connections.get(user_id, set()))

    closed: list[WebSocket] = []
    for ws in sockets:
        try:
            await ws.send_json(envelope)
        except Exception:  # noqa: BLE001
            closed.append(ws)

    if closed:
        async with _registry_lock:
            bucket = _connections.get(user_id, set())
            for ws in closed:
                bucket.discard(ws)


def broadcast_sync_event(user_id: str, event: str, data: dict[str, Any]) -> None:
    """Thread-safe fire-and-forget wrapper callable from sync Celery workers.

    Workers run in a separate thread (no running event loop).  This helper
    schedules the coroutine on the running loop if one exists, or silently
    skips if the API process has no active loop (e.g. during tests).
    """
    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(broadcast_to_user(user_id, event, data), loop=loop)
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _authenticate_token(token: str) -> str | None:
    """Return user_id string on success, None on any failure."""
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        parsed = uuid.UUID(user_id_str)
    except (ValueError, Exception):  # noqa: BLE001
        return None

    try:
        with SessionLocal() as db:
            user = db.execute(
                select(User).where(User.id == parsed)
            ).scalar_one_or_none()
            return str(user.id) if user else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    user_id = _authenticate_token(token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("WS connected: user=%s", user_id)

    # Register connection
    async with _registry_lock:
        if user_id not in _connections:
            _connections[user_id] = set()
        _connections[user_id].add(websocket)

    # Send welcome event
    await websocket.send_json({
        "event": "connected",
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "data": {"message": "Connected"},
    })

    try:
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("WS disconnected: user=%s", user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("WS error for user %s: %s", user_id, exc)
    finally:
        async with _registry_lock:
            bucket = _connections.get(user_id, set())
            bucket.discard(websocket)
