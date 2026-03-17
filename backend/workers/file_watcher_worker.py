from __future__ import annotations

import logging
from typing import Any

from workers.celery_app import QUEUE_EMBEDDING, celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="workers.file_watcher_worker.watch_file_changes", bind=True)
def watch_file_changes(self, item_id: str, user_id: str, source: str) -> dict[str, Any]:
    try:
        embedding_task = celery_app.send_task(
            "workers.embedding_worker.embed_item",
            args=[item_id, user_id, None],
            queue=QUEUE_EMBEDDING,
        )
    except Exception:
        logger.exception(
            "Failed to queue embedding task from file watcher. item_id=%s user_id=%s source=%s",
            item_id,
            user_id,
            source,
        )
        raise

    return {
        "status": "queued",
        "pipeline": "file-watcher",
        "item_id": item_id,
        "user_id": user_id,
        "source": source,
        "task_id": self.request.id,
        "embedding_task_id": embedding_task.id,
    }
