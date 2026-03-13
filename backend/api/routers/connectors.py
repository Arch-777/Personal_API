from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.db import get_db
from api.models.connector import Connector
from api.models.user import User
from api.schemas.connector import ConnectorResponse, ConnectorSyncResponse
from workers.celery_app import celery_app


router = APIRouter(prefix="/connectors", tags=["connectors"])

PLATFORM_TO_TASK = {
    "gmail": "workers.google_worker.sync_gmail",
    "drive": "workers.google_worker.sync_drive",
    "gcal": "workers.google_worker.sync_gcal",
    "whatsapp": "workers.whatsapp_worker.sync_whatsapp",
    "notion": "workers.notion_worker.sync_notion",
    "spotify": "workers.spotify_worker.sync_spotify",
}


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    connector.status = "syncing"
    connector.error_message = None
    db.commit()

    celery_app.send_task(
        task_name,
        args=[str(connector.id), str(current_user.id), connector.sync_cursor],
    )

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
