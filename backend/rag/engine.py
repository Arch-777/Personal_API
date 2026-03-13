from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from rag.context import BuiltContext, ContextBuilder
from rag.embedder import DeterministicEmbedder
from rag.retriever import HybridRetriever


class RAGEngine:
	def __init__(
		self,
		db: Session,
		user_id: uuid.UUID,
		embedder: DeterministicEmbedder | None = None,
		retriever: HybridRetriever | None = None,
		context_builder: ContextBuilder | None = None,
	):
		self.db = db
		self.user_id = user_id
		self.embedder = embedder or DeterministicEmbedder()
		self.retriever = retriever or HybridRetriever(db)
		self.context_builder = context_builder or ContextBuilder()

	def query(self, query: str, top_k: int = 8, type_filter: str | None = None) -> dict[str, Any]:
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
		)

		built: BuiltContext = self.context_builder.build(normalized_query, retrieved)
		answer = self.context_builder.compose_answer(normalized_query, retrieved)

		return {
			"answer": answer,
			"sources": built.sources,
			"documents": built.documents,
			"file_links": built.file_links,
			"context": built.context_text,
		}

