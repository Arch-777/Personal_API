from __future__ import annotations

from dataclasses import dataclass

from rag.retriever import RetrievedItem


@dataclass(slots=True)
class BuiltContext:
	context_text: str
	sources: list[dict]
	documents: list[str]
	file_links: list[str]


class ContextBuilder:
	def build(self, query: str, retrieved: list[RetrievedItem], max_sources: int = 8) -> BuiltContext:
		selected = retrieved[:max_sources]

		context_lines: list[str] = []
		sources: list[dict] = []
		documents: list[str] = []
		file_links: list[str] = []

		for index, item in enumerate(selected, start=1):
			preview = item.preview
			context_lines.append(
				f"[{index}] ({item.source}/{item.type}) score={item.score:.3f} id={item.id} :: {preview}"
			)

			sources.append(
				{
					"id": item.id,
					"type": item.type,
					"source": item.source,
					"score": float(item.score),
					"preview": preview,
				}
			)

			documents.append(item.title or item.id)

			link = _extract_link(item)
			if link and link not in file_links:
				file_links.append(link)

		context_text = "\n".join(context_lines)
		return BuiltContext(
			context_text=context_text,
			sources=sources,
			documents=documents,
			file_links=file_links,
		)

	def compose_answer(self, query: str, retrieved: list[RetrievedItem]) -> str:
		if not retrieved:
			return "I could not find relevant items in your personal knowledge base yet. Try a more specific query or sync more sources."

		top_items = retrieved[:3]
		answer_lines = [f"I found {len(retrieved)} relevant item(s) for '{query}'."]
		for item in top_items:
			label = item.title or item.id
			detail = item.preview or "No preview available."
			answer_lines.append(f"- {label} ({item.source}/{item.type}): {detail}")

		answer_lines.append("Use the listed sources for verification or follow-up questions.")
		return "\n".join(answer_lines)


def _extract_link(item: RetrievedItem) -> str | None:
	metadata = item.metadata or {}
	for key in ["web_view_link", "web_link", "html_link", "external_url", "file_path"]:
		value = metadata.get(key)
		if isinstance(value, str) and value.strip():
			return value
	if isinstance(item.file_path, str) and item.file_path.strip():
		return item.file_path
	return None

