from __future__ import annotations

from dataclasses import dataclass
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
	max_tokens: int = 512,
	overlap_tokens: int = 50,
	chunk_id_prefix: str = "chunk",
	metadata: dict[str, Any] | None = None,
) -> list[TextChunk]:
	"""Split text into overlapping token windows.

	Tokenization is whitespace-based to avoid external dependencies.
	"""
	normalized = " ".join(text.split())
	if not normalized:
		return []

	safe_max_tokens = max(1, max_tokens)
	safe_overlap = max(0, min(overlap_tokens, safe_max_tokens - 1))
	stride = safe_max_tokens - safe_overlap

	tokens = normalized.split(" ")
	chunks: list[TextChunk] = []

	index = 0
	start = 0
	base_metadata = dict(metadata or {})

	while start < len(tokens):
		end = min(start + safe_max_tokens, len(tokens))
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
	max_tokens: int = 512,
	overlap_tokens: int = 50,
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

