from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(slots=True)
class TextChunk:
	chunk_id: str
	index: int
	text: str
	token_count: int
	metadata: dict[str, Any]


def chunk_text(
	text: str,
	max_tokens: int = 240,
	overlap_tokens: int = 40,
	chunk_id_prefix: str = "chunk",
	metadata: dict[str, Any] | None = None,
) -> list[TextChunk]:
	"""Split text into sentence-aware overlapping token windows.

	Tokenization remains whitespace-based to avoid external dependencies.
	"""
	segments = _prepare_segments(text)
	if not segments:
		return []

	safe_max_tokens = max(1, max_tokens)
	safe_overlap = max(0, min(overlap_tokens, safe_max_tokens - 1))
	stride = safe_max_tokens - safe_overlap

	tokens = " ".join(segments).split(" ")
	chunks: list[TextChunk] = []

	index = 0
	start = 0
	base_metadata = dict(metadata or {})

	while start < len(tokens):
		end = _find_preferred_boundary(tokens=tokens, start=start, max_tokens=safe_max_tokens)
		chunk_tokens = tokens[start:end]
		chunk_text_value = " ".join(chunk_tokens)
		chunk_metadata = dict(base_metadata)
		chunk_metadata.update(
			{
				"token_start": start,
				"token_end": end,
				"chunk_index": index,
			}
		)

		chunks.append(
			TextChunk(
				chunk_id=f"{chunk_id_prefix}:{index}",
				index=index,
				text=chunk_text_value,
				token_count=len(chunk_tokens),
				metadata=chunk_metadata,
			)
		)

		index += 1
		start += stride

	return chunks


def chunk_item_content(
	item_id: str,
	content: str,
	source: str,
	item_type: str,
	max_tokens: int = 240,
	overlap_tokens: int = 40,
) -> list[TextChunk]:
	return chunk_text(
		text=content,
		max_tokens=max_tokens,
		overlap_tokens=overlap_tokens,
		chunk_id_prefix=f"item:{item_id}",
		metadata={
			"item_id": item_id,
			"source": source,
			"type": item_type,
		},
	)


def _prepare_segments(text: str) -> list[str]:
	raw = (text or "").strip()
	if not raw:
		return []

	paragraphs = [part.strip() for part in re.split(r"\n{2,}", raw) if part.strip()]
	segments: list[str] = []
	for paragraph in paragraphs:
		sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
		if not sentences:
			continue
		segments.extend(sentences)

	if not segments:
		segments = [" ".join(raw.split())]

	return [" ".join(segment.split()) for segment in segments if segment.strip()]


def _find_preferred_boundary(tokens: list[str], start: int, max_tokens: int) -> int:
	hard_end = min(start + max_tokens, len(tokens))
	if hard_end >= len(tokens):
		return hard_end

	for index in range(hard_end, min(hard_end + 24, len(tokens))):
		token = tokens[index - 1]
		if token.endswith((".", "?", "!")):
			return index

	return hard_end

