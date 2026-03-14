from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from api.core.config import get_settings
from rag.context import BuiltContext, ContextBuilder
from rag.embedder import DeterministicEmbedder
from rag.generator import OllamaGenerator
from rag.retriever import HybridRetriever


logger = logging.getLogger(__name__)


class RAGEngine:
	def __init__(
		self,
		db: Session,
		user_id: uuid.UUID,
		embedder: DeterministicEmbedder | None = None,
		retriever: HybridRetriever | None = None,
		context_builder: ContextBuilder | None = None,
		generator: OllamaGenerator | None = None,
		use_llm: bool | None = None,
	):
		settings = get_settings()
		self.db = db
		self.user_id = user_id
		self.embedder = embedder or DeterministicEmbedder()
		self.retriever = retriever or HybridRetriever(db)
		self.context_builder = context_builder or ContextBuilder()
		self.use_llm = settings.rag_llm_enabled if use_llm is None else use_llm
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

	def query(self, query: str, top_k: int = 8, type_filter: str | None = None, include_debug: bool = False) -> dict[str, Any]:
		normalized_query = " ".join(query.split()).strip()
		if not normalized_query:
			return {
				"answer": "Please provide a query.",
				"sources": [],
				"documents": [],
				"file_links": [],
				"context": "",
			}

		query_embedding = self.embedder.embed_text(normalized_query)
		retrieved = self.retriever.retrieve(
			user_id=self.user_id,
			query=normalized_query,
			top_k=top_k,
			type_filter=type_filter,
			query_embedding=query_embedding,
			include_debug=include_debug,
		)

		built: BuiltContext = self.context_builder.build(normalized_query, retrieved, include_debug=include_debug)
		answer = self.context_builder.compose_answer(normalized_query, retrieved)
		answer_mode = "deterministic"

		if self.use_llm and self.generator is not None and built.sources:
			try:
				answer = self.generator.generate(query=normalized_query, context_text=built.context_text)
				answer_mode = "llm"
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
		}

