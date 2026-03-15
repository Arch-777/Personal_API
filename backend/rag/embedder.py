from __future__ import annotations

import hashlib
import logging
import math


logger = logging.getLogger(__name__)


class DeterministicEmbedder:
	"""Deterministic embedding generator for local/offline environments."""

	def __init__(self, dimensions: int = 1536):
		self.dimensions = max(8, dimensions)

	def embed_text(self, text: str) -> list[float]:
		normalized = " ".join(text.split()).strip().lower()
		if not normalized:
			return [0.0] * self.dimensions

		values: list[float] = []
		block = 0

		while len(values) < self.dimensions:
			digest = hashlib.sha256(f"{normalized}|{block}".encode("utf-8")).digest()
			for index in range(0, len(digest), 2):
				pair = digest[index : index + 2]
				if len(pair) < 2:
					continue
				raw = int.from_bytes(pair, byteorder="big", signed=False)
				values.append((raw / 32767.5) - 1.0)
				if len(values) == self.dimensions:
					break
			block += 1

		return _l2_normalize(values)

	def embed_texts(self, texts: list[str]) -> list[list[float]]:
		return [self.embed_text(text) for text in texts]


class SemanticEmbedder:
	"""Semantic embedder with lightweight local model support and deterministic fallback."""

	def __init__(
		self,
		provider: str = "fastembed",
		model_name: str = "BAAI/bge-small-en-v1.5",
		dimensions: int = 1536,
	):
		self.provider = (provider or "deterministic").strip().lower()
		self.model_name = (model_name or "BAAI/bge-small-en-v1.5").strip()
		self.dimensions = max(8, int(dimensions))
		self._fallback = DeterministicEmbedder(dimensions=self.dimensions)
		self._embedding_model = None

		if self.provider == "deterministic":
			return

		if self.provider == "fastembed":
			try:
				from fastembed import TextEmbedding  # type: ignore

				self._embedding_model = TextEmbedding(model_name=self.model_name)
			except Exception as exc:  # noqa: BLE001
				logger.warning(
					"Semantic embedder provider initialization failed; falling back to deterministic embeddings: %s",
					exc,
				)
				self.provider = "deterministic"
				self._embedding_model = None
			return

		logger.warning("Unknown embedding provider '%s'; using deterministic fallback", self.provider)
		self.provider = "deterministic"

	def embed_text(self, text: str) -> list[float]:
		return self.embed_texts([text])[0]

	def embed_texts(self, texts: list[str]) -> list[list[float]]:
		if not texts:
			return []

		if self.provider != "fastembed" or self._embedding_model is None:
			return self._fallback.embed_texts(texts)

		normalized_texts = [" ".join(text.split()).strip() for text in texts]
		try:
			raw_vectors = list(self._embedding_model.embed(normalized_texts))
		except Exception as exc:  # noqa: BLE001
			logger.warning(
				"Semantic embedding generation failed; using deterministic fallback for this batch: %s",
				exc,
			)
			return self._fallback.embed_texts(texts)

		vectors: list[list[float]] = []
		for vector in raw_vectors:
			values = [float(value) for value in vector]
			values = _fit_dimensions(values, self.dimensions)
			vectors.append(_l2_normalize(values))

		if len(vectors) != len(texts):
			return self._fallback.embed_texts(texts)
		return vectors


def cosine_similarity(vector_a: list[float] | None, vector_b: list[float] | None) -> float:
	if not vector_a or not vector_b:
		return 0.0
	if len(vector_a) != len(vector_b):
		return 0.0

	numerator = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
	denom_a = math.sqrt(sum(a * a for a in vector_a))
	denom_b = math.sqrt(sum(b * b for b in vector_b))
	if denom_a == 0 or denom_b == 0:
		return 0.0
	return numerator / (denom_a * denom_b)


def _l2_normalize(vector: list[float]) -> list[float]:
	norm = math.sqrt(sum(value * value for value in vector))
	if norm == 0:
		return [0.0 for _ in vector]
	return [value / norm for value in vector]


def _fit_dimensions(vector: list[float], dimensions: int) -> list[float]:
	if len(vector) == dimensions:
		return vector
	if len(vector) > dimensions:
		return vector[:dimensions]
	return vector + [0.0] * (dimensions - len(vector))

