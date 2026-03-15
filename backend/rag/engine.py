from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from api.core.config import get_settings
from rag.context import BuiltContext, ContextBuilder
from rag.embedder import SemanticEmbedder
from rag.generator import OllamaGenerator
from rag.query_rewriter import QueryRewriter
from rag.reranker import LightweightReranker
from rag.retriever import HybridRetriever


logger = logging.getLogger(__name__)


class RAGEngine:
	def __init__(
		self,
		db: Session,
		user_id: uuid.UUID,
		embedder: SemanticEmbedder | None = None,
		retriever: HybridRetriever | None = None,
		context_builder: ContextBuilder | None = None,
		generator: OllamaGenerator | None = None,
		query_rewriter: QueryRewriter | None = None,
		reranker: LightweightReranker | None = None,
		use_llm: bool | None = None,
	):
		settings = get_settings()
		self.db = db
		self.user_id = user_id
		self.embedder = embedder or SemanticEmbedder(
			provider=settings.rag_embedding_provider,
			model_name=settings.rag_embedding_model,
			dimensions=settings.rag_embedding_dimensions,
		)
		self.retriever = retriever or HybridRetriever(
			db,
			semantic_candidate_limit=settings.rag_semantic_candidate_limit,
			lexical_candidate_limit=settings.rag_lexical_candidate_limit,
			rrf_k=settings.rag_rrf_k,
			rrf_semantic_weight=settings.rag_rrf_semantic_weight,
			rrf_lexical_weight=settings.rag_rrf_lexical_weight,
			rrf_boost=settings.rag_rrf_boost,
		)
		self.context_builder = context_builder or ContextBuilder()
		self.use_llm = settings.rag_llm_enabled if use_llm is None else use_llm
		self.query_rewriter = query_rewriter or QueryRewriter(
			enabled=settings.rag_query_rewrite_enabled,
			max_variants=settings.rag_query_rewrite_max_variants,
		)
		self.reranker = reranker or LightweightReranker(
			enabled=settings.rag_reranker_enabled,
			top_n=settings.rag_reranker_top_n,
			weight=settings.rag_reranker_weight,
		)
		self.min_top_score = float(settings.rag_grounding_min_top_score)
		self.min_avg_score = float(settings.rag_grounding_min_avg_score)
		self.generator = generator
		if self.use_llm and self.generator is None:
			if settings.rag_llm_provider.strip().lower() == "ollama":
				self.generator = OllamaGenerator(
					base_url=settings.rag_llm_base_url,
					model=settings.rag_llm_model,
					timeout_seconds=settings.rag_llm_timeout_seconds,
					temperature=settings.rag_llm_temperature,
					max_tokens=settings.rag_llm_max_tokens,
					system_prompt=settings.rag_llm_system_prompt,
				)

	def query(
		self,
		query: str,
		top_k: int = 8,
		type_filter: str | None = None,
		include_debug: bool = False,
		conversation_history: list[dict[str, str]] | None = None,
	) -> dict[str, Any]:
		normalized_query = " ".join(query.split()).strip()
		if not normalized_query:
			return {
				"answer": "Please provide a query.",
				"sources": [],
				"documents": [],
				"file_links": [],
				"context": "",
			}

		if _is_general_knowledge_query(normalized_query):
			return {
				"answer": (
					"> ℹ️ I can only answer questions grounded in your **personal data** "
					"(emails, repositories, documents, calendar, Spotify, etc.).\n\n"
					"This looks like a general knowledge question — I’m not able to help with that."
				),
				"answer_mode": "out_of_scope",
				"sources": [],
				"documents": [],
				"file_links": [],
				"context": "",
				"grounding": {"source_count": 0, "top_score": 0.0, "avg_top3_score": 0.0},
			}

		retrieval_query = _compose_retrieval_query(normalized_query, conversation_history)
		date_after = _parse_temporal_filter(normalized_query)

		retrieved = self._retrieve_with_rewrites(
			query=retrieval_query,
			top_k=top_k,
			type_filter=type_filter,
			include_debug=include_debug,
			date_after=date_after,
		)
		retrieved = self.reranker.rerank(normalized_query, retrieved, include_debug=include_debug)

		# Semantic dedup: keep best-scoring chunk per item ID for answer diversity
		seen_item_ids: set[str] = set()
		deduped: list[Any] = []
		for item in retrieved:
			if item.id not in seen_item_ids:
				seen_item_ids.add(item.id)
				deduped.append(item)
		retrieved = deduped

		built: BuiltContext = self.context_builder.build(normalized_query, retrieved, include_debug=include_debug)
		grounding = _grounding_confidence(retrieved)
		answer = self.context_builder.compose_answer(normalized_query, retrieved)
		answer_mode = "deterministic"

		if not _is_grounded_enough(
			grounding=grounding,
			min_top_score=self.min_top_score,
			min_avg_score=self.min_avg_score,
		):
			answer_mode = "abstain"
			answer = self.context_builder.compose_abstain_answer(normalized_query, retrieved)
			return {
				"answer": answer,
				"answer_mode": answer_mode,
				"sources": built.sources,
				"documents": built.documents,
				"file_links": built.file_links,
				"context": built.context_text,
				"grounding": grounding,
			}

		if self.use_llm and self.generator is not None and built.sources:
			try:
				llm_answer = self.generator.generate(query=normalized_query, context_text=built.context_text)
				if _has_valid_citations(llm_answer, source_count=len(built.sources)):
					answer = llm_answer
					answer_mode = "llm"
				else:
					logger.warning(
						"LLM answer missing/invalid citations; falling back to deterministic RAG answer",
						extra={"source_count": len(built.sources)},
					)
					answer = self.context_builder.compose_answer(normalized_query, retrieved)
					answer_mode = "fallback"
			except httpx.TimeoutException as exc:
				logger.warning(
					"LLM generation timed out; falling back to deterministic RAG answer: %s",
					exc,
				)
				answer = self.context_builder.compose_answer(normalized_query, retrieved)
				answer_mode = "fallback"
			except Exception:
				logger.exception("LLM generation failed; falling back to deterministic RAG answer")
				# Fall back to deterministic answer path when local LLM is unavailable.
				answer = self.context_builder.compose_answer(normalized_query, retrieved)
				answer_mode = "fallback"

		logger.info(
			"RAG answer generated",
			extra={
				"answer_mode": answer_mode,
				"use_llm": self.use_llm,
				"source_count": len(built.sources),
				"document_count": len(built.documents),
			},
		)

		return {
			"answer": answer,
			"answer_mode": answer_mode,
			"sources": built.sources,
			"documents": built.documents,
			"file_links": built.file_links,
			"context": built.context_text,
			"grounding": grounding,
		}

	def _retrieve_with_rewrites(
		self,
		query: str,
		top_k: int,
		type_filter: str | None,
		include_debug: bool,
		date_after: "datetime | None" = None,
	):
		variants = self.query_rewriter.rewrite(query)
		if not variants:
			variants = [query]

		merged_by_key: dict[str, Any] = {}
		for variant in variants:
			query_embedding = self.embedder.embed_text(variant)
			results = self.retriever.retrieve(
				user_id=self.user_id,
				query=variant,
				top_k=max(top_k * 2, 10),
				type_filter=type_filter,
				query_embedding=query_embedding,
				include_debug=include_debug,
				date_after=date_after,
			)
			for item in results:
				identity = f"{item.id}:{item.chunk_id or ''}:{item.chunk_index if item.chunk_index is not None else ''}"
				existing = merged_by_key.get(identity)
				if existing is None or item.score > existing.score:
					if include_debug:
						item.debug["query_variant"] = variant
					merged_by_key[identity] = item

		merged = list(merged_by_key.values())
		merged.sort(key=lambda item: item.score, reverse=True)
		return merged[: max(top_k * 2, top_k)]


def _grounding_confidence(retrieved: list[Any]) -> dict[str, float | int]:
	if not retrieved:
		return {
			"source_count": 0,
			"top_score": 0.0,
			"avg_top3_score": 0.0,
		}

	top_score = float(retrieved[0].score)
	top_slice = retrieved[:3]
	avg_score = sum(float(item.score) for item in top_slice) / max(len(top_slice), 1)
	return {
		"source_count": len(retrieved),
		"top_score": top_score,
		"avg_top3_score": avg_score,
	}


def _is_grounded_enough(grounding: dict[str, float | int], min_top_score: float, min_avg_score: float) -> bool:
	source_count = int(grounding.get("source_count", 0) or 0)
	top_score = float(grounding.get("top_score", 0.0) or 0.0)
	avg_score = float(grounding.get("avg_top3_score", 0.0) or 0.0)
	if source_count <= 0:
		return False
	if top_score < min_top_score:
		return False
	if avg_score < min_avg_score:
		return False
	# Score spread check: if all top chunks are equally mediocre (no clear winner), abstain
	if top_score < (min_top_score * 1.3) and abs(top_score - avg_score) < 0.04:
		return False
	return True


# ---------------------------------------------------------------------------
# Query domain guard — intercept obvious general-knowledge questions before
# retrieval so they never pass the grounding check with unrelated chunks.
# ---------------------------------------------------------------------------

_GENERAL_KNOWLEDGE_RE = re.compile(
	r"""
	\b(
	  what\s+is\s+the\s+(capital|population|area|currency|language|president|prime\s+minister)
	| (capital|population|currency|area|timezone)\s+of\b
	| who\s+(is|was|were|invented|discovered|founded|wrote|created|directed|painted)\b
	| when\s+(was|did|were|is)\b.{0,30}\b(born|die|founded|invented|discovered|built|created|released)
	| where\s+is\b.{0,20}\b(located|situated|found)
	| how\s+(does|do|did|many|much|far|long|tall|heavy)\b
	| (define|definition\s+of|meaning\s+of|explain)\b
	| (history|origin)\s+of\b
	| (convert|translate)\s+\d
	| weather\s+(in|for|at)\b
	| (time|date)\s+(in|at|for)\b
	| (exchange|conversion)\s+rate
	| formula\s+for\b
	| (largest|smallest|highest|lowest|fastest|oldest|newest)\s+(country|city|mountain|river|ocean|planet)
	| \d+\s*(cm|mm|km|miles?|kg|lbs?|pounds?|celsius|fahrenheit|dollars?|euros?)\s+(to|in)\b
	)\b
	""",
	re.IGNORECASE | re.VERBOSE,
)


def _is_general_knowledge_query(query: str) -> bool:
	"""Return True if the query is clearly asking for general world knowledge
	rather than personal data. Used as an early short-circuit before retrieval."""
	return bool(_GENERAL_KNOWLEDGE_RE.search(query))


# ---------------------------------------------------------------------------
# Temporal filter — parse natural language time expressions into a cutoff date
# ---------------------------------------------------------------------------

_MONTH_NAMES = {
	"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
	"july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
	"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
	"aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_temporal_filter(query: str) -> "datetime | None":
	"""Return a UTC datetime cutoff if the query contains a recognisable time expression,
	otherwise return None."""
	q = query.lower()
	now = datetime.now(tz=timezone.utc)

	# "last N days / weeks / months"
	m = re.search(r"last\s+(\d+)\s+(day|days|week|weeks|month|months)", q)
	if m:
		n = int(m.group(1))
		unit = m.group(2)
		if "month" in unit:
			return now - timedelta(days=n * 30)
		if "week" in unit:
			return now - timedelta(weeks=n)
		return now - timedelta(days=n)

	# "yesterday"
	if re.search(r"\byesterday\b", q):
		return now - timedelta(days=2)

	# "today"
	if re.search(r"\btoday\b", q):
		return now - timedelta(days=1)

	# "this week" / "past week" / "last week"
	if re.search(r"\b(this|past|last)\s+week\b", q):
		return now - timedelta(days=7)

	# "this month" / "past month" / "last month"
	if re.search(r"\b(this|past|last)\s+month\b", q):
		return now - timedelta(days=30)

	# "recently" / "recent"
	if re.search(r"\b(recently|recent)\b", q):
		return now - timedelta(days=14)

	# "in March" / "in January 2025" etc.
	m = re.search(r"\bin\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)(?:\s+(\d{4}))?\b", q)
	if m:
		month_num = _MONTH_NAMES.get(m.group(1), 1)
		year = int(m.group(2)) if m.group(2) else now.year
		try:
			cutoff = datetime(year, month_num, 1, tzinfo=timezone.utc)
			# If the requested month is in the future relative to now, don't filter
			if cutoff > now:
				return None
			return cutoff
		except ValueError:
			pass

	return None


def _compose_retrieval_query(query: str, conversation_history: list[dict[str, str]] | None, max_turns: int = 3) -> str:
	"""Blend the current query with a compact session context to improve follow-up retrieval."""
	if not conversation_history:
		return query

	segments: list[str] = []
	for message in conversation_history[-(max_turns * 2):]:
		role = str(message.get("role", "")).strip().lower()
		content = " ".join(str(message.get("content", "")).split()).strip()
		# Use user turns only to avoid retrieval drift from assistant phrasing.
		if role != "user" or not content:
			continue
		segments.append(f"{role}: {content[:180]}")

	if not segments:
		return query

	return f"{query}\nContext from current session: {' | '.join(segments)}"


def _has_valid_citations(answer: str, source_count: int) -> bool:
	if source_count <= 0:
		return False

	citations = _extract_citation_indices(answer)
	if not citations:
		return False

	return all(1 <= citation <= source_count for citation in citations)


def _extract_citation_indices(answer: str) -> set[int]:
	if not answer or not answer.strip():
		return set()

	indices: set[int] = set()
	for match in re.findall(r"\[(\d+)\]", answer):
		try:
			indices.add(int(match))
		except ValueError:
			continue
	return indices

