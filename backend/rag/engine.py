from __future__ import annotations

import copy
import logging
import re
import time
import uuid
from collections import OrderedDict
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


class _TTLCache:
	def __init__(self, max_size: int, ttl_seconds: int):
		self.max_size = max(1, int(max_size))
		ttl = int(ttl_seconds)
		self.ttl_seconds = max(1, ttl)
		self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

	def get(self, key: str) -> Any | None:
		now = time.monotonic()
		entry = self._store.get(key)
		if entry is None:
			return None
		expires_at, value = entry
		if expires_at <= now:
			self._store.pop(key, None)
			return None
		self._store.move_to_end(key)
		return copy.deepcopy(value)

	def set(self, key: str, value: Any) -> None:
		expires_at = time.monotonic() + float(self.ttl_seconds)
		self._store[key] = (expires_at, copy.deepcopy(value))
		self._store.move_to_end(key)
		while len(self._store) > self.max_size:
			self._store.popitem(last=False)


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
		failover_generator: OllamaGenerator | None = None,
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
		self.neighbor_chunk_enabled = bool(settings.rag_neighbor_chunk_enabled)
		self.neighbor_chunk_window = max(0, int(settings.rag_neighbor_chunk_window))
		self.context_max_tokens = max(128, int(settings.rag_context_max_tokens))
		self.citation_claim_verification_enabled = bool(settings.rag_citation_claim_verification_enabled)
		self.citation_claim_min_token_overlap = max(0.0, float(settings.rag_citation_claim_min_token_overlap))
		self.min_top_score = float(settings.rag_grounding_min_top_score)
		self.min_avg_score = float(settings.rag_grounding_min_avg_score)
		self.cache_enabled = bool(settings.rag_cache_enabled)
		self.query_embedding_cache: _TTLCache | None = None
		self.retrieval_cache: _TTLCache | None = None
		if self.cache_enabled:
			self.query_embedding_cache = _TTLCache(
				max_size=settings.rag_query_embedding_cache_max_size,
				ttl_seconds=settings.rag_query_embedding_cache_ttl_seconds,
			)
			self.retrieval_cache = _TTLCache(
				max_size=settings.rag_retrieval_cache_max_size,
				ttl_seconds=settings.rag_retrieval_cache_ttl_seconds,
			)

		self.llm_circuit_breaker_enabled = bool(settings.rag_llm_circuit_breaker_enabled)
		self.llm_circuit_breaker_failure_threshold = max(1, int(settings.rag_llm_circuit_breaker_failure_threshold))
		self.llm_circuit_breaker_cooldown_seconds = max(5, int(settings.rag_llm_circuit_breaker_cooldown_seconds))
		self._llm_failures = 0
		self._llm_circuit_open_until = 0.0
		self.llm_failover_enabled = bool(settings.rag_llm_failover_enabled)
		self.generator = generator
		self.failover_generator = failover_generator
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

		if (
			self.use_llm
			and self.llm_failover_enabled
			and self.failover_generator is None
			and settings.rag_llm_failover_provider.strip().lower() == "ollama"
			and settings.rag_llm_failover_base_url.strip()
			and settings.rag_llm_failover_model.strip()
		):
			self.failover_generator = OllamaGenerator(
				base_url=settings.rag_llm_failover_base_url,
				model=settings.rag_llm_failover_model,
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
		query_start = time.perf_counter()
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

		retrieval_start = time.perf_counter()
		retrieved = self._retrieve_with_rewrites(
			query=retrieval_query,
			top_k=top_k,
			type_filter=type_filter,
			include_debug=include_debug,
			date_after=date_after,
		)
		retrieval_elapsed_ms = round((time.perf_counter() - retrieval_start) * 1000.0, 3)

		expand_start = time.perf_counter()
		retrieved = self._expand_neighbor_context(retrieved, include_debug=include_debug)
		expand_elapsed_ms = round((time.perf_counter() - expand_start) * 1000.0, 3)

		rerank_start = time.perf_counter()
		retrieved = self.reranker.rerank(normalized_query, retrieved, include_debug=include_debug)
		rerank_elapsed_ms = round((time.perf_counter() - rerank_start) * 1000.0, 3)

		# Semantic dedup: keep best-scoring chunk per item ID for answer diversity
		seen_item_ids: set[str] = set()
		deduped: list[Any] = []
		for item in retrieved:
			if item.id not in seen_item_ids:
				seen_item_ids.add(item.id)
				deduped.append(item)
		retrieved = deduped
		retrieved = _apply_context_token_budget(retrieved, max_tokens=self.context_max_tokens)

		context_start = time.perf_counter()
		built: BuiltContext = self.context_builder.build(normalized_query, retrieved, include_debug=include_debug)
		context_elapsed_ms = round((time.perf_counter() - context_start) * 1000.0, 3)
		grounding = _grounding_confidence(retrieved)
		answer = self.context_builder.compose_answer(normalized_query, retrieved)
		answer_mode = "deterministic"
		generation_elapsed_ms = 0.0

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
			if self._is_llm_circuit_open():
				logger.warning("LLM circuit breaker is open; using deterministic fallback answer")
				answer = self.context_builder.compose_answer(normalized_query, retrieved)
				answer_mode = "fallback"
			else:
				try:
					generation_start = time.perf_counter()
					llm_answer, provider_used = self._generate_with_failover(
						query=normalized_query,
						context_text=built.context_text,
					)
					generation_elapsed_ms = round((time.perf_counter() - generation_start) * 1000.0, 3)
					if _is_llm_answer_verified(
						answer=llm_answer,
						sources=built.sources,
						claim_verification_enabled=self.citation_claim_verification_enabled,
						min_claim_overlap=self.citation_claim_min_token_overlap,
					):
						answer = llm_answer
						answer_mode = "llm"
						if include_debug:
							for source in built.sources:
								if isinstance(source, dict):
									source.setdefault("debug", {})
									source["debug"]["llm_provider_used"] = provider_used
						self._on_llm_success()
					else:
						logger.warning(
							"LLM answer missing/invalid citations; falling back to deterministic RAG answer",
							extra={"source_count": len(built.sources)},
						)
						self._on_llm_failure("invalid_citations")
						answer = self.context_builder.compose_answer(normalized_query, retrieved)
						answer_mode = "fallback"
				except httpx.TimeoutException as exc:
					logger.warning(
						"LLM generation timed out; falling back to deterministic RAG answer: %s",
						exc,
					)
					self._on_llm_failure("timeout")
					answer = self.context_builder.compose_answer(normalized_query, retrieved)
					answer_mode = "fallback"
				except Exception:
					logger.exception("LLM generation failed; falling back to deterministic RAG answer")
					self._on_llm_failure("exception")
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
				"timings_ms": {
					"retrieval": retrieval_elapsed_ms,
					"neighbor_expand": expand_elapsed_ms,
					"rerank": rerank_elapsed_ms,
					"context_build": context_elapsed_ms,
					"generation": generation_elapsed_ms,
					"total": round((time.perf_counter() - query_start) * 1000.0, 3),
				},
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
			"timings": {
				"retrieval_ms": retrieval_elapsed_ms,
				"neighbor_expand_ms": expand_elapsed_ms,
				"rerank_ms": rerank_elapsed_ms,
				"context_build_ms": context_elapsed_ms,
				"generation_ms": generation_elapsed_ms,
				"total_ms": round((time.perf_counter() - query_start) * 1000.0, 3),
			},
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
			query_embedding = self._embed_query_cached(variant)
			results = self._retrieve_variant_cached(
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

	def _embed_query_cached(self, query: str) -> list[float]:
		if self.query_embedding_cache is None:
			return self.embedder.embed_text(query)

		cache_key = f"embedding:{query}"
		cached = self.query_embedding_cache.get(cache_key)
		if cached is not None:
			return cached

		embedding = self.embedder.embed_text(query)
		self.query_embedding_cache.set(cache_key, embedding)
		return embedding

	def _retrieve_variant_cached(
		self,
		query: str,
		top_k: int,
		type_filter: str | None,
		query_embedding: list[float],
		include_debug: bool,
		date_after: datetime | None,
	):
		if self.retrieval_cache is None:
			return self.retriever.retrieve(
				user_id=self.user_id,
				query=query,
				top_k=top_k,
				type_filter=type_filter,
				query_embedding=query_embedding,
				include_debug=include_debug,
				date_after=date_after,
			)

		cache_key = (
			f"retrieval:{self.user_id}:{query}:{top_k}:{type_filter or ''}:"
			f"{1 if include_debug else 0}:{date_after.isoformat() if date_after else ''}"
		)
		cached = self.retrieval_cache.get(cache_key)
		if cached is not None:
			return cached

		results = self.retriever.retrieve(
			user_id=self.user_id,
			query=query,
			top_k=top_k,
			type_filter=type_filter,
			query_embedding=query_embedding,
			include_debug=include_debug,
			date_after=date_after,
		)
		self.retrieval_cache.set(cache_key, results)
		return results

	def _is_llm_circuit_open(self) -> bool:
		if not self.llm_circuit_breaker_enabled:
			return False
		return time.monotonic() < self._llm_circuit_open_until

	def _on_llm_success(self) -> None:
		self._llm_failures = 0
		self._llm_circuit_open_until = 0.0

	def _on_llm_failure(self, reason: str) -> None:
		if not self.llm_circuit_breaker_enabled:
			return
		self._llm_failures += 1
		if self._llm_failures < self.llm_circuit_breaker_failure_threshold:
			return

		self._llm_circuit_open_until = time.monotonic() + float(self.llm_circuit_breaker_cooldown_seconds)
		logger.warning(
			"LLM circuit breaker opened",
			extra={
				"failure_reason": reason,
				"failure_count": self._llm_failures,
				"cooldown_seconds": self.llm_circuit_breaker_cooldown_seconds,
			},
		)

	def _generate_with_failover(self, query: str, context_text: str) -> tuple[str, str]:
		if self.generator is None:
			raise RuntimeError("LLM generator is not configured")

		try:
			return self.generator.generate(query=query, context_text=context_text), "primary"
		except Exception:
			if not self.llm_failover_enabled or self.failover_generator is None:
				raise
			logger.warning("Primary LLM provider failed, attempting failover provider")
			return self.failover_generator.generate(query=query, context_text=context_text), "failover"

	def _expand_neighbor_context(self, retrieved: list[Any], include_debug: bool = False):
		if not self.neighbor_chunk_enabled:
			return retrieved
		if self.neighbor_chunk_window <= 0:
			return retrieved

		expand_method = getattr(self.retriever, "expand_with_neighbor_chunks", None)
		if not callable(expand_method):
			return retrieved

		try:
			return expand_method(retrieved, window=self.neighbor_chunk_window, include_debug=include_debug)
		except TypeError:
			# Backward compatibility with custom retriever stubs that may not accept include_debug.
			try:
				return expand_method(retrieved, window=self.neighbor_chunk_window)
			except Exception:
				logger.exception("Neighbor chunk expansion failed; continuing without expansion")
				return retrieved
		except Exception:
			logger.exception("Neighbor chunk expansion failed; continuing without expansion")
			return retrieved


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


def _estimate_result_tokens(item: Any) -> int:
	parts = [
		getattr(item, "title", "") or "",
		getattr(item, "summary", "") or "",
		getattr(item, "chunk_text", "") or "",
		getattr(item, "content", "") or "",
	]
	text = " ".join(str(part) for part in parts if part)
	return max(1, len(text.split()))


def _apply_context_token_budget(retrieved: list[Any], max_tokens: int) -> list[Any]:
	if not retrieved:
		return retrieved
	safe_budget = max(64, int(max_tokens))

	selected: list[Any] = []
	used_tokens = 0
	for index, item in enumerate(retrieved):
		token_estimate = _estimate_result_tokens(item)
		if index == 0:
			selected.append(item)
			used_tokens += token_estimate
			continue
		if used_tokens + token_estimate > safe_budget:
			break
		selected.append(item)
		used_tokens += token_estimate

	return selected


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


def _is_llm_answer_verified(
	*,
	answer: str,
	sources: list[dict],
	claim_verification_enabled: bool,
	min_claim_overlap: float,
) -> bool:
	if not _has_valid_citations(answer, source_count=len(sources)):
		return False
	if not claim_verification_enabled:
		return True
	return _claims_align_with_sources(answer=answer, sources=sources, min_overlap=min_claim_overlap)


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


def _claims_align_with_sources(answer: str, sources: list[dict], min_overlap: float) -> bool:
	if not answer.strip():
		return False

	by_index: dict[int, str] = {}
	for index, source in enumerate(sources, start=1):
		preview = source.get("preview") if isinstance(source, dict) else ""
		if isinstance(preview, str):
			by_index[index] = preview.lower()

	for raw_line in answer.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		citations = _extract_citation_indices(line)
		if not citations:
			continue

		claim_tokens = _tokenize_for_alignment(re.sub(r"\[\d+\]", " ", line))
		if not claim_tokens:
			continue

		max_overlap = 0.0
		for citation in citations:
			source_preview = by_index.get(citation, "")
			if not source_preview:
				continue
			source_tokens = _tokenize_for_alignment(source_preview)
			if not source_tokens:
				continue
			overlap = len(claim_tokens & source_tokens) / max(len(claim_tokens), 1)
			if overlap > max_overlap:
				max_overlap = overlap

		if max_overlap < max(0.01, min_overlap):
			return False

	return True


def _tokenize_for_alignment(text: str) -> set[str]:
	tokens = set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))
	return {token for token in tokens if token not in {"with", "from", "this", "that", "there", "their", "about", "your"}}

