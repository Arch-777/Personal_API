from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.models.item import Item
from rag.embedder import cosine_similarity


@dataclass(slots=True)
class RetrievedItem:
	id: str
	type: str
	source: str
	title: str | None
	content: str | None
	summary: str | None
	metadata: dict
	item_date: datetime | None
	file_path: str | None
	score: float

	@property
	def preview(self) -> str:
		text = self.summary or self.content or self.title or ""
		return text[:320]


class HybridRetriever:
	def __init__(self, db: Session):
		self.db = db

	def retrieve(
		self,
		user_id: uuid.UUID,
		query: str,
		top_k: int = 8,
		type_filter: str | None = None,
		query_embedding: list[float] | None = None,
		candidate_limit: int = 200,
	) -> list[RetrievedItem]:
		normalized_query = " ".join(query.split()).strip().lower()
		if not normalized_query:
			return []

		query_tokens = _tokenize(normalized_query)
		query_token_list = list(query_tokens)

		stmt = select(Item).where(Item.user_id == user_id)
		if type_filter:
			stmt = stmt.where(Item.type == type_filter)

		if query_tokens:
			like_filters = []
			for token in query_token_list[:8]:
				like_term = f"%{token}%"
				like_filters.extend(
					[
						Item.title.ilike(like_term),
						Item.summary.ilike(like_term),
						Item.content.ilike(like_term),
					]
				)
			stmt = stmt.where(or_(*like_filters))

		stmt = stmt.order_by(Item.item_date.desc().nullslast(), Item.created_at.desc()).limit(max(20, candidate_limit))
		rows = self.db.execute(stmt).scalars().all()

		scored: list[RetrievedItem] = []
		for row in rows:
			score = _score_item(row, normalized_query, query_tokens, query_embedding)
			if score <= 0:
				continue

			scored.append(
				RetrievedItem(
					id=str(row.id),
					type=row.type,
					source=row.source,
					title=row.title,
					content=row.content,
					summary=row.summary,
					metadata=row.metadata_json or {},
					item_date=row.item_date,
					file_path=row.file_path,
					score=score,
				)
			)

		scored.sort(key=lambda item: (item.score, item.item_date or datetime.min), reverse=True)
		return scored[:top_k]


def _score_item(
	row: Item,
	normalized_query: str,
	query_tokens: set[str],
	query_embedding: list[float] | None,
) -> float:
	title_text = _normalize(row.title)
	summary_text = _normalize(row.summary)
	content_text = _normalize(row.content)
	combined = " ".join([part for part in [title_text, summary_text, content_text] if part])

	if not combined:
		return 0.0

	doc_tokens = _tokenize(combined)
	if not doc_tokens:
		return 0.0

	overlap = len(query_tokens & doc_tokens)
	lexical_score = overlap / max(len(query_tokens), 1)
	phrase_bonus = 0.35 if normalized_query in combined else 0.0
	title_bonus = 0.2 if normalized_query in title_text else 0.0

	embedding_bonus = 0.0
	if isinstance(row.embedding, list) and query_embedding:
		embedding_bonus = max(0.0, cosine_similarity(query_embedding, row.embedding))

	return float(lexical_score + phrase_bonus + title_bonus + (embedding_bonus * 0.5))


def _normalize(value: str | None) -> str:
	if not value:
		return ""
	return " ".join(value.lower().split())


def _tokenize(text: str) -> set[str]:
	tokens = [token.strip(".,;:!?()[]{}\"'`") for token in text.split()]
	return {token for token in tokens if token}

