from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select

from api.core.config import get_settings
from api.core.db import SessionLocal
from api.models.connector import Connector
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

PLATFORM_TO_TASK: dict[str, str] = {
    "gmail": "workers.google_worker.sync_gmail",
    "drive": "workers.google_worker.sync_drive",
    "gcal": "workers.google_worker.sync_gcal",
    "notion": "workers.notion_worker.sync_notion",
    "spotify": "workers.spotify_worker.sync_spotify",
    "slack": "workers.slack_worker.sync_slack",
}


def _connector_auto_sync_enabled(connector: Connector) -> bool:
    metadata = connector.metadata_json if isinstance(connector.metadata_json, dict) else {}
    raw_value = metadata.get("auto_sync_enabled")
    if isinstance(raw_value, bool):
        return raw_value
    return True


@celery_app.task(name="workers.auto_sync_worker.dispatch_auto_sync", queue="default")
def dispatch_auto_sync() -> dict[str, Any]:
    """Queue sync jobs for connected integrations that are stale.

    This task is intended to run from Celery Beat on a short interval.
    """
    settings = get_settings()
    if not settings.auto_sync_enabled:
        return {"status": "skipped", "reason": "auto_sync_disabled"}

    stale_before = datetime.now(UTC) - timedelta(minutes=settings.auto_sync_stale_after_minutes)

    with SessionLocal() as db:
        connectors = db.execute(
            select(Connector)
            .where(
                Connector.platform.in_(tuple(PLATFORM_TO_TASK.keys())),
                Connector.status.in_(("connected", "error")),
                or_(Connector.last_synced.is_(None), Connector.last_synced <= stale_before),
            )
            .order_by(Connector.last_synced.asc().nullsfirst(), Connector.created_at.asc())
            .limit(settings.auto_sync_batch_size)
        ).scalars().all()

    eligible_connectors = [connector for connector in connectors if _connector_auto_sync_enabled(connector)]

    queued = 0
    failed = 0
    for connector in eligible_connectors:
        task_name = PLATFORM_TO_TASK.get(connector.platform)
        if task_name is None:
            continue

        try:
            celery_app.send_task(
                task_name,
                args=[str(connector.id), str(connector.user_id), connector.sync_cursor],
            )
            queued += 1
        except Exception:  # noqa: BLE001
            failed += 1
            logger.exception(
                "Failed to queue auto sync for connector_id=%s platform=%s",
                connector.id,
                connector.platform,
            )

    return {
        "status": "completed",
        "scanned": len(connectors),
        "eligible": len(eligible_connectors),
        "queued": queued,
        "failed": failed,
        "stale_before": stale_before.isoformat(),
    }
