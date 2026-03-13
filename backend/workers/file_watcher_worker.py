from __future__ import annotations

from typing import Any

from workers.celery_app import celery_app


@celery_app.task(name="workers.file_watcher_worker.watch_file_changes", bind=True)
def watch_file_changes(self, item_id: str, user_id: str, source: str) -> dict[str, Any]:
    embedding_task = celery_app.send_task(
        "workers.embedding_worker.embed_item",
        args=[item_id, user_id, None],
    )
    return {
        "status": "queued",
        "pipeline": "file-watcher",
        "item_id": item_id,
        "user_id": user_id,
        "source": source,
        "task_id": self.request.id,
        "embedding_task_id": embedding_task.id,
    }
