from __future__ import annotations

import hashlib
import math


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

