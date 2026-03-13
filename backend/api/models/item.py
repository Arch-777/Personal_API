import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.core.db import Base


class Item(Base):
	__tablename__ = "items"
	__table_args__ = (
		UniqueConstraint("user_id", "source", "source_id", name="uq_items_user_source_source_id"),
		Index("idx_items_user_type_date", "user_id", "type", "item_date"),
	)

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	type: Mapped[str] = mapped_column(Text, nullable=False)
	source: Mapped[str] = mapped_column(Text, nullable=False, index=True)
	source_id: Mapped[str] = mapped_column(Text, nullable=False)
	title: Mapped[str | None] = mapped_column(Text, nullable=True)
	sender_name: Mapped[str | None] = mapped_column(Text, nullable=True)
	sender_email: Mapped[str | None] = mapped_column(Text, nullable=True)
	content: Mapped[str | None] = mapped_column(Text, nullable=True)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
	item_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
	embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
	content_tsv: Mapped[str | None] = mapped_column(
		TSVECTOR,
		Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))", persisted=True),
		nullable=True,
	)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)

