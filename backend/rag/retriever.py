from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Float, and_, cast, or_, select
from sqlalchemy.orm import Session

from api.models.item import Item
from api.models.item_chunk import ItemChunk
from rag.embedder import cosine_similarity


STOPWORDS = {
	"a",
	"an",
	"any",
	"are",
	"for",
	"from",
	"i",
	"in",
	"is",
	"it",
	"me",
	"my",
	"of",
	"on",
	"please",
	"show",
	"the",
	"to",
	"was",
	"were",
	"what",
	"with",
	"you",
}

EMAIL_HINT_TOKENS = {"mail", "email", "gmail", "inbox", "message", "messages"}
LINKEDIN_HINT_TOKENS = {"linkedin", "linkedin.com"}


@dataclass(slots=True)
class RetrievedItem:
	id: str
	type: str
	source: str
	source_id: str | None = None
	title: str | None = None
	content: str | None = None
	summary: str | None = None
	metadata: dict = field(default_factory=dict)
	item_date: datetime | None = None
	file_path: str | None = None
	score: float = 0.0
	chunk_id: str | None = None
	chunk_index: int | None = None
	chunk_text: str | None = None
	canonical_key: str | None = None
	debug: dict = field(default_factory=dict)

	@property
	def preview(self) -> str:
		text = self.chunk_text or self.summary or self.content or self.title or ""
		return text[:320]


@dataclass(slots=True)
class QueryIntent:
	prefers_spotify: bool = False
	prefers_email: bool = False
	prefers_documents: bool = False
	mentions_linkedin: bool = False
	wants_favorites: bool = False
	wants_tracks: bool = False
	requests_recent: bool = False
	requested_count: int | None = None


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
		query_keywords = _remove_stopwords(query_tokens)
		intent = _infer_intent(normalized_query, query_tokens)
		active_tokens = query_keywords if query_keywords else query_tokens
		query_token_list = list(active_tokens)

		if intent.requests_recent:
			effective_limit = intent.requested_count or top_k
			return self._retrieve_recent_items(
				user_id=user_id,
				top_k=max(1, min(effective_limit, 50)),
				type_filter=type_filter,
				intent=intent,
			)

		chunk_candidates = self._retrieve_chunk_candidates(
			user_id=user_id,
			query_embedding=query_embedding,
			type_filter=type_filter,
			candidate_limit=candidate_limit,
			intent=intent,
		)

		stmt = select(Item).where(Item.user_id == user_id)
		if type_filter:
			stmt = stmt.where(Item.type == type_filter)

		source_constraint = _build_source_constraint(intent)
		if source_constraint is not None:
			stmt = stmt.where(source_constraint)

		if active_tokens:
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
			if like_filters:
				stmt = stmt.where(or_(*like_filters))

		stmt = stmt.order_by(Item.item_date.desc().nullslast(), Item.created_at.desc()).limit(max(20, candidate_limit))
		rows = self.db.execute(stmt).scalars().all()

		scored: list[RetrievedItem] = []
		seen_item_ids = {candidate.id for candidate in chunk_candidates}
		for row in rows:
			if str(row.id) in seen_item_ids:
				continue
			if not _matches_intent_source(row_source=row.source, row_type=row.type, intent=intent):
				continue
			score = _score_item(
				row=row,
				normalized_query=normalized_query,
				query_tokens=query_tokens,
				query_keywords=query_keywords,
				intent=intent,
				query_embedding=query_embedding,
			)
			if score <= 0:
				continue

			scored.append(
				RetrievedItem(
					id=str(row.id),
					type=row.type,
					source=row.source,
						source_id=getattr(row, "source_id", None),
					title=row.title,
					content=row.content,
					summary=row.summary,
					metadata=row.metadata_json or {},
					item_date=row.item_date,
					file_path=row.file_path,
					score=score,
					canonical_key=_canonical_group_key(
						source=row.source,
							source_id=getattr(row, "source_id", None),
						title=row.title,
						metadata=row.metadata_json or {},
							sender_name=getattr(row, "sender_name", None),
					),
				)
			)

		combined = chunk_candidates + scored
		deduped = _dedupe_and_group(combined)
		reranked = _rerank_grouped_results(deduped, intent=intent)
		reranked.sort(key=lambda item: (item.score, item.item_date or datetime.min), reverse=True)
		return reranked[:top_k]

	def _retrieve_chunk_candidates(
		self,
		user_id: uuid.UUID,
		query_embedding: list[float] | None,
		type_filter: str | None,
		candidate_limit: int,
		intent: QueryIntent,
	) -> list[RetrievedItem]:
		if not query_embedding:
			return []

		try:
			distance_expr = cast(ItemChunk.embedding.cosine_distance(query_embedding), Float).label("distance")
			stmt = (
				select(ItemChunk, Item, distance_expr)
				.join(Item, ItemChunk.item_id == Item.id)
				.where(
					ItemChunk.user_id == user_id,
					ItemChunk.embedding.is_not(None),
				)
			)
			if type_filter:
				stmt = stmt.where(Item.type == type_filter)
			source_constraint = _build_source_constraint(intent)
			if source_constraint is not None:
				stmt = stmt.where(source_constraint)
			stmt = stmt.order_by(distance_expr.asc()).limit(max(20, candidate_limit))
			rows = self.db.execute(stmt).all()
		except Exception:
			return []

		results: list[RetrievedItem] = []
		for row in rows:
			chunk = getattr(row, "ItemChunk", None) or row[0]
			item = getattr(row, "Item", None) or row[1]
			if not _matches_intent_source(row_source=item.source, row_type=item.type, intent=intent):
				continue
			distance = getattr(row, "distance", None)
			if distance is None and len(row) > 2:
				distance = row[2]
			score = max(0.0, 1.0 - float(distance or 1.0))
			results.append(
				RetrievedItem(
					id=str(item.id),
					type=item.type,
					source=item.source,
					source_id=item.source_id,
					title=item.title,
					content=item.content,
					summary=item.summary,
					metadata=item.metadata_json or {},
					item_date=item.item_date,
					file_path=item.file_path,
					score=score,
					chunk_id=chunk.chunk_id,
					chunk_index=chunk.chunk_index,
					chunk_text=chunk.chunk_text,
					canonical_key=_canonical_group_key(
						source=item.source,
						source_id=item.source_id,
						title=item.title,
						metadata=item.metadata_json or {},
						sender_name=item.sender_name,
					),
					debug={"distance": float(distance or 1.0)},
				)
			)
		return results

	def _retrieve_recent_items(
		self,
		user_id: uuid.UUID,
		top_k: int,
		type_filter: str | None,
		intent: QueryIntent,
	) -> list[RetrievedItem]:
		stmt = select(Item).where(Item.user_id == user_id)
		if type_filter:
			stmt = stmt.where(Item.type == type_filter)
		source_constraint = _build_source_constraint(intent)
		if source_constraint is not None:
			stmt = stmt.where(source_constraint)

		stmt = stmt.order_by(Item.item_date.desc().nullslast(), Item.created_at.desc()).limit(max(1, top_k * 3))
		rows = self.db.execute(stmt).scalars().all()

		results: list[RetrievedItem] = []
		for idx, row in enumerate(rows):
			if not _matches_intent_source(row_source=row.source, row_type=row.type, intent=intent):
				continue
			score = max(0.001, 1.0 - (idx * 0.03))
			results.append(
				RetrievedItem(
					id=str(row.id),
					type=row.type,
					source=row.source,
					source_id=getattr(row, "source_id", None),
					title=row.title,
					content=row.content,
					summary=row.summary,
					metadata=row.metadata_json or {},
					item_date=row.item_date,
					file_path=row.file_path,
					score=score,
					canonical_key=_canonical_group_key(
						source=row.source,
						source_id=getattr(row, "source_id", None),
						title=row.title,
						metadata=row.metadata_json or {},
						sender_name=getattr(row, "sender_name", None),
					),
				)
			)

		deduped = _dedupe_and_group(results)
		deduped.sort(key=lambda item: (item.item_date or datetime.min, item.score), reverse=True)
		return deduped[:top_k]


def _score_item(
	row: Item,
	normalized_query: str,
	query_tokens: set[str],
	query_keywords: set[str],
	intent: QueryIntent,
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

	active_query_tokens = query_keywords if query_keywords else query_tokens
	overlap = len(active_query_tokens & doc_tokens)
	lexical_score = overlap / max(len(active_query_tokens), 1)
	phrase_bonus = 0.35 if normalized_query in combined else 0.0
	title_bonus = 0.2 if normalized_query in title_text else 0.0

	embedding_bonus = 0.0
	if isinstance(row.embedding, list) and query_embedding:
		embedding_bonus = max(0.0, cosine_similarity(query_embedding, row.embedding))

	intent_bonus = _intent_bonus(
		row=row,
		query_tokens=query_tokens,
		combined_text=combined,
		intent=intent,
	)

	return float(lexical_score + phrase_bonus + title_bonus + (embedding_bonus * 0.5) + intent_bonus)


def _intent_bonus(row: Item, query_tokens: set[str], combined_text: str, intent: QueryIntent) -> float:
	bonus = 0.0

	row_type = (row.type or "").lower()
	row_source = (row.source or "").lower()
	metadata = row.metadata_json or {}

	if intent.prefers_email:
		if row_type == "email" or row_source == "gmail":
			bonus += 0.35
		else:
			bonus -= 0.1

	if intent.mentions_linkedin:
		if "linkedin" in combined_text:
			bonus += 0.45
		elif row_source in {"spotify"}:
			bonus -= 0.15

	if intent.prefers_spotify:
		if row_source == "spotify":
			bonus += 0.45
			if intent.wants_tracks and row_type in {"track", "media"}:
				bonus += 0.2
		else:
			bonus -= 0.2

	if intent.wants_favorites and row_source == "spotify":
		bonus += _favorite_metadata_score(metadata)

	return bonus


def _favorite_metadata_score(metadata: dict) -> float:
	bonus = 0.0
	if not isinstance(metadata, dict):
		return bonus

	if metadata.get("liked") is True:
		bonus += 0.5

	play_count = metadata.get("play_count")
	if isinstance(play_count, (int, float)):
		bonus += min(float(play_count) / 50.0, 0.6)

	popularity = metadata.get("popularity")
	if isinstance(popularity, (int, float)):
		bonus += min(float(popularity) / 200.0, 0.4)

	top_rank = metadata.get("top_rank")
	if isinstance(top_rank, (int, float)) and top_rank > 0:
		bonus += max(0.0, 0.7 - (float(top_rank) * 0.05))

	return bonus


def _normalize(value: str | None) -> str:
	if not value:
		return ""
	return " ".join(value.lower().split())


def _tokenize(text: str) -> set[str]:
	raw_tokens = [token.strip(".,;:!?()[]{}\"'`") for token in text.split()]
	tokens: set[str] = set()
	for raw in raw_tokens:
		if not raw:
			continue
		alpha_parts = re.findall(r"[a-z]+", raw)
		if not alpha_parts:
			tokens.add(raw)
			continue
		for part in alpha_parts:
			normalized = _normalize_token(part)
			if normalized:
				tokens.add(normalized)
	return tokens


def _remove_stopwords(tokens: set[str]) -> set[str]:
	return {token for token in tokens if token not in STOPWORDS}


def _normalize_token(token: str) -> str:
	if token in {"mails", "emails", "gmails"}:
		return token[:-1]
	if token in {"messages", "documents", "tracks", "songs", "favourites", "favorites"}:
		return token[:-1]
	return token


def _infer_intent(normalized_query: str, query_tokens: set[str]) -> QueryIntent:
	requested_count = _extract_requested_count(normalized_query)
	requests_recent = bool(query_tokens & {"last", "latest", "recent", "newest"}) or "last" in normalized_query

	return QueryIntent(
		prefers_spotify="spotify" in query_tokens,
		prefers_email=bool(query_tokens & EMAIL_HINT_TOKENS),
		prefers_documents=bool(query_tokens & {"document", "documents", "note", "notes", "page", "pages"}),
		mentions_linkedin=bool(query_tokens & LINKEDIN_HINT_TOKENS),
		wants_favorites=bool(query_tokens & {"favorite", "favourite", "favorites", "favourites", "best", "top"}),
		wants_tracks=bool(query_tokens & {"song", "songs", "track", "tracks", "music"}),
		requests_recent=requests_recent,
		requested_count=requested_count,
	)


def _extract_requested_count(normalized_query: str) -> int | None:
	match = re.search(r"(?:last|latest|recent|newest)\s*(\d{1,2})", normalized_query)
	if match:
		return max(1, min(int(match.group(1)), 50))

	standalone = re.search(r"\b(\d{1,2})\b", normalized_query)
	if standalone and any(word in normalized_query for word in ["mail", "email", "gmail", "song", "track", "document"]):
		return max(1, min(int(standalone.group(1)), 50))
	return None


def _build_source_constraint(intent: QueryIntent):
	if intent.prefers_email and not intent.prefers_spotify and not intent.prefers_documents:
		return or_(Item.source == "gmail", Item.type == "email")
	if intent.prefers_spotify and not intent.prefers_email and not intent.prefers_documents:
		return Item.source == "spotify"
	if intent.prefers_documents and not intent.prefers_email and not intent.prefers_spotify:
		return or_(Item.source.in_(["drive", "notion"]), Item.type.in_(["document", "note", "page", "file"]))
	return None


def _matches_intent_source(*, row_source: str | None, row_type: str | None, intent: QueryIntent) -> bool:
	source = (row_source or "").lower()
	type_name = (row_type or "").lower()
	if intent.prefers_email and not intent.prefers_spotify and not intent.prefers_documents:
		return source == "gmail" or type_name == "email"
	if intent.prefers_spotify and not intent.prefers_email and not intent.prefers_documents:
		return source == "spotify"
	if intent.prefers_documents and not intent.prefers_email and not intent.prefers_spotify:
		return source in {"drive", "notion"} or type_name in {"document", "note", "page", "file"}
	return True


def _dedupe_and_group(results: list[RetrievedItem]) -> list[RetrievedItem]:
	best_by_key: dict[str, RetrievedItem] = {}
	for result in results:
		key = result.canonical_key or result.id
		existing = best_by_key.get(key)
		if existing is None or result.score > existing.score:
			best_by_key[key] = result
	return list(best_by_key.values())


def _rerank_grouped_results(results: list[RetrievedItem], intent: QueryIntent) -> list[RetrievedItem]:
	for result in results:
		adjustment = 0.0
		metadata = result.metadata or {}
		if intent.prefers_spotify:
			adjustment += 0.4 if result.source == "spotify" else -0.2
		if intent.prefers_email:
			adjustment += 0.4 if result.source == "gmail" or result.type == "email" else -0.1
		if intent.wants_favorites and result.source == "spotify":
			adjustment += _favorite_metadata_score(metadata)
		if intent.mentions_linkedin:
			text = " ".join(
				[
					(result.title or "").lower(),
					(result.summary or "").lower(),
					(result.content or "").lower(),
					(result.chunk_text or "").lower(),
				]
			)
			if "linkedin" in text:
				adjustment += 0.5
		result.score += adjustment
	return results


def _canonical_group_key(
	*,
	source: str,
	source_id: str | None,
	title: str | None,
	metadata: dict,
	sender_name: str | None,
) -> str:
	if source == "spotify":
		track_id = metadata.get("track_id") if isinstance(metadata, dict) else None
		if isinstance(track_id, str) and track_id.strip():
			return f"spotify:track:{track_id.strip()}"
		artist_names = metadata.get("artist_names") if isinstance(metadata, dict) else None
		artist_key = ",".join(sorted([str(name).strip().lower() for name in artist_names])) if isinstance(artist_names, list) else (sender_name or "")
		title_key = (title or metadata.get("track_name") or source_id or "unknown").strip().lower()
		return f"spotify:title:{title_key}|artist:{artist_key}"

	base_source_id = (source_id or title or "unknown").strip().lower()
	return f"{source}:{base_source_id}"

