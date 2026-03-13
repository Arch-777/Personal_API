import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.core.db import Base


class ItemChunk(Base):
	__tablename__ = "item_chunks"
	__table_args__ = (
		UniqueConstraint("item_id", "chunk_index", name="uq_item_chunks_item_chunk_index"),
		Index("idx_item_chunks_user_item", "user_id", "item_id"),
		Index("idx_item_chunks_user_created", "user_id", "created_at"),
	)

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	chunk_id: Mapped[str] = mapped_column(Text, nullable=False)
	chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
	chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
	token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
	metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
	embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
	content_tsv: Mapped[str | None] = mapped_column(
		TSVECTOR,
		Computed("to_tsvector('english', coalesce(chunk_text, ''))", persisted=True),
		nullable=True,
	)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)