from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from api.core.db import SessionLocal
from api.models.item import Item
from api.models.item_chunk import ItemChunk
from rag.indexer import index_item_chunks
from workers.celery_app import celery_app


@celery_app.task(name="workers.embedding_worker.embed_item", bind=True)
def embed_item(self, item_id: str, user_id: str, chunk_count: int | None = None) -> dict[str, Any]:
    parsed_item_id = uuid.UUID(item_id)
    parsed_user_id = uuid.UUID(user_id)

    with SessionLocal() as db:
        item = db.execute(
            select(Item).where(Item.id == parsed_item_id, Item.user_id == parsed_user_id)
        ).scalar_one_or_none()
        if item is None:
            raise ValueError("Item not found for embedding")

        metadata = dict(item.metadata_json or {})
        stored_chunk_count = metadata.get("chunk_count")
        try:
            expected_chunk_count = int(stored_chunk_count or 0)
        except (TypeError, ValueError):
            expected_chunk_count = 0

        existing_chunk_count = db.scalar(
            select(func.count()).select_from(ItemChunk).where(ItemChunk.item_id == parsed_item_id)
        ) or 0

        if (
            metadata.get("embedding_status") == "completed"
            and expected_chunk_count > 0
            and int(existing_chunk_count) >= expected_chunk_count
        ):
            return {
                "status": "skipped",
                "pipeline": "embedding",
                "item_id": item_id,
                "user_id": user_id,
                "task_id": self.request.id,
            }

        indexing = index_item_chunks(db=db, item=item)
        metadata["embedding_status"] = "completed"
        metadata["embedded_at"] = datetime.now(UTC).isoformat()
        metadata["chunk_count"] = chunk_count if chunk_count is not None else indexing.chunk_count
        item.metadata_json = metadata

        db.commit()

    return {
        "status": "completed",
        "pipeline": "embedding",
        "item_id": item_id,
        "user_id": user_id,
        "task_id": self.request.id,
    }
