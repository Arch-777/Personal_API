from __future__ import annotations

import re

from rag.retriever import RetrievedItem


class LightweightReranker:
	"""Low-cost heuristic reranker to improve top-k precision."""

	def __init__(self, enabled: bool = True, weight: float = 0.35, top_n: int = 24):
		self.enabled = bool(enabled)
		self.weight = max(0.0, float(weight))
		self.top_n = max(1, int(top_n))

	def rerank(self, query: str, items: list[RetrievedItem], include_debug: bool = False) -> list[RetrievedItem]:
		if not self.enabled or not items:
			return items

		query_tokens = set(_tokens(query))
		query_phrase = " ".join(query.split()).strip().lower()
		if not query_tokens:
			return items

		pivot = min(len(items), self.top_n)
		head = list(items[:pivot])
		tail = list(items[pivot:])

		for item in head:
			text = _candidate_text(item)
			tokens = set(_tokens(text))
			coverage = len(query_tokens & tokens) / max(len(query_tokens), 1)
			phrase_bonus = 0.35 if query_phrase and query_phrase in text else 0.0
			position_bonus = _ordered_token_bonus(query_tokens, text)
			rerank_score = coverage + phrase_bonus + position_bonus
			item.score += rerank_score * self.weight
			if include_debug:
				item.debug["reranker_score"] = round(rerank_score, 6)
				item.debug["reranker_weight"] = round(self.weight, 6)
				item.debug["reranker_applied"] = True

		head.sort(key=lambda result: result.score, reverse=True)
		return head + tail


def _candidate_text(item: RetrievedItem) -> str:
	parts = [item.title or "", item.summary or "", item.chunk_text or "", item.content or ""]
	return " ".join(part.strip().lower() for part in parts if part and part.strip())


def _tokens(text: str) -> list[str]:
	return re.findall(r"[a-z0-9]+", (text or "").lower())


def _ordered_token_bonus(query_tokens: set[str], text: str) -> float:
	if not query_tokens:
		return 0.0
	positions: list[int] = []
	for token in query_tokens:
		idx = text.find(token)
		if idx >= 0:
			positions.append(idx)
	if len(positions) <= 1:
		return 0.0
	positions.sort()
	gaps = [positions[index + 1] - positions[index] for index in range(len(positions) - 1)]
	avg_gap = sum(gaps) / max(len(gaps), 1)
	if avg_gap <= 16:
		return 0.2
	if avg_gap <= 32:
		return 0.1
	return 0.0
