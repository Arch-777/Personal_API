from __future__ import annotations

from typing import Any

from workers.celery_app import celery_app
from workers.connector_sync import run_connector_sync


@celery_app.task(name="workers.google_worker.sync_gmail", bind=True)
def sync_gmail(self, connector_id: str, user_id: str, cursor: str | None = None) -> dict[str, Any]:
    return run_connector_sync(platform="gmail", connector_id=connector_id, user_id=user_id, cursor=cursor)


@celery_app.task(name="workers.google_worker.sync_drive", bind=True)
def sync_drive(self, connector_id: str, user_id: str, cursor: str | None = None) -> dict[str, Any]:
    return run_connector_sync(platform="drive", connector_id=connector_id, user_id=user_id, cursor=cursor)


@celery_app.task(name="workers.google_worker.sync_gcal", bind=True)
def sync_gcal(self, connector_id: str, user_id: str, cursor: str | None = None) -> dict[str, Any]:
    return run_connector_sync(platform="gcal", connector_id=connector_id, user_id=user_id, cursor=cursor)
