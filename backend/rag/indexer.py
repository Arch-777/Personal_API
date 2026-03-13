from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from api.models.item import Item
from api.models.item_chunk import ItemChunk
from rag.chunker import chunk_item_content
from rag.embedder import DeterministicEmbedder


@dataclass(slots=True)
class IndexingResult:
	chunk_count: int
	item_embedding: list[float] | None


def index_item_chunks(db: Session, item: Item, embedder: DeterministicEmbedder | None = None) -> IndexingResult:
	embedder = embedder or DeterministicEmbedder()
	content = _build_index_text(item)
	chunks = chunk_item_content(
		item_id=str(item.id),
		content=content,
		source=item.source,
		item_type=item.type,
	)

	db.execute(delete(ItemChunk).where(ItemChunk.item_id == item.id))

	if not chunks:
		item.embedding = None
		return IndexingResult(chunk_count=0, item_embedding=None)

	embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
	now = datetime.now(UTC)
	rows: list[ItemChunk] = []
	for chunk, embedding in zip(chunks, embeddings, strict=False):
		chunk_metadata = dict(chunk.metadata)
		chunk_metadata.update(
			{
				"source_id": item.source_id,
				"title": item.title,
				"file_path": item.file_path,
			}
		)
		rows.append(
			ItemChunk(
				item_id=item.id,
				user_id=item.user_id,
				chunk_id=chunk.chunk_id,
				chunk_index=chunk.index,
				chunk_text=chunk.text,
				token_count=chunk.token_count,
				metadata_json=chunk_metadata,
				embedding=embedding,
				updated_at=now,
			)
		)

	db.add_all(rows)
	item.embedding = _average_embeddings(embeddings)
	return IndexingResult(chunk_count=len(rows), item_embedding=item.embedding)


def _build_index_text(item: Item) -> str:
	parts = [item.title, item.summary, item.content]
	if item.source == "spotify":
		metadata = item.metadata_json or {}
		album = metadata.get("album") if isinstance(metadata, dict) else None
		artist_names = metadata.get("artist_names") if isinstance(metadata, dict) else None
		if isinstance(artist_names, list) and artist_names:
			parts.append(", ".join([str(name) for name in artist_names if name]))
		if isinstance(album, str) and album.strip():
			parts.append(f"Album: {album.strip()}")
	return "\n".join([part.strip() for part in parts if isinstance(part, str) and part.strip()])


def _average_embeddings(embeddings: list[list[float]]) -> list[float] | None:
	if not embeddings:
		return None
	dimensions = len(embeddings[0])
	sums = [0.0] * dimensions
	for embedding in embeddings:
		for index, value in enumerate(embedding):
			sums[index] += value
	count = float(len(embeddings))
	return [value / count for value in sums]