from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from rag.retriever import RetrievedItem


_SOURCE_EMOJI: dict[str, str] = {
	"gmail": "📬",
	"github": "💻",
	"notion": "📝",
	"spotify": "🎵",
	"slack": "💬",
	"drive": "📁",
	"gcal": "📅",
}
_SOURCE_LABEL: dict[str, str] = {
	"gmail": "Emails",
	"github": "GitHub",
	"notion": "Notion",
	"spotify": "Spotify",
	"slack": "Slack",
	"drive": "Google Drive",
	"gcal": "Calendar",
}
_TYPE_LABEL: dict[str, str] = {
	"track": "tracks",
	"repository": "repositories",
	"email": "emails",
	"document": "documents",
	"message": "messages",
	"event": "events",
	"file": "files",
	"playlist": "playlists",
}


@dataclass(slots=True)
class BuiltContext:
	context_text: str
	sources: list[dict]
	documents: list[str]
	file_links: list[str]


class ContextBuilder:
	def build(self, query: str, retrieved: list[RetrievedItem], max_sources: int = 8, include_debug: bool = False) -> BuiltContext:
		selected = retrieved[:max_sources]

		context_lines: list[str] = []
		sources: list[dict] = []
		documents: list[str] = []
		file_links: list[str] = []

		for index, item in enumerate(selected, start=1):
			preview = _clean_preview(item.preview)
			context_lines.append(
				f"[{index}] ({item.source}/{item.type}) score={item.score:.3f} id={item.id} :: {preview}"
			)

			source_entry = {
				"id": item.id,
				"type": item.type,
				"source": item.source,
				"score": float(item.score),
				"preview": preview,
			}
			if include_debug and item.debug:
				source_entry["debug"] = item.debug
			sources.append(source_entry)

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
		query_tokens = _query_tokens(query)
		message_mode = bool(query_tokens & {"message", "messages", "chat", "dm", "dms", "slack"})

		if not retrieved:
			if "slack" in query_tokens:
				return (
					"> **No Slack messages found yet.**\n\n"
					"Sync your Slack connector, then try: *\"last 5 Slack messages from #engineering\"*"
				)
			return (
				"> **No results found in your personal knowledge base.**\n\n"
				"Try a more specific query or sync more sources."
			)

		if message_mode:
			return _compose_message_digest_md(query=query, retrieved=retrieved)

		source_counts = Counter(item.source for item in retrieved)
		type_counts = Counter(item.type for item in retrieved)
		dominant_source = source_counts.most_common(1)[0][0]
		dominant_type = type_counts.most_common(1)[0][0]

		emoji = _SOURCE_EMOJI.get(dominant_source, "🔍")
		section_label = _SOURCE_LABEL.get(dominant_source, dominant_source.title())

		items_lines: list[str] = []
		for index, item in enumerate(retrieved[:4], start=1):
			if item.source == "spotify" or item.type == "track":
				items_lines.append(_format_track_item(item, index))
			elif item.type == "repository":
				items_lines.append(_format_repo_item(item, index))
			elif item.source == "gmail" or item.type == "email":
				items_lines.append(_format_email_item(item, index))
			elif item.source in ("notion", "drive") or item.type in ("document", "file"):
				items_lines.append(_format_doc_item(item, index))
			elif item.source == "gcal" or item.type == "event":
				items_lines.append(_format_event_item(item, index))
			else:
				items_lines.append(_format_generic_item(item, index))

		unique_sources = [s for s, _ in source_counts.most_common()]
		source_str = " · ".join(unique_sources[:3])
		count_label = f"{len(retrieved)} {_TYPE_LABEL.get(dominant_type, 'results')}"
		footer = f"> {count_label} · {source_str}"

		parts: list[str] = [
			f"### {emoji} {section_label}",
			"",
			"Here's what I found in your indexed data:",
			"",
		]
		parts.extend(items_lines)
		parts.extend(["", "---", footer])
		return "\n".join(parts)

	def compose_abstain_answer(self, query: str, retrieved: list[RetrievedItem]) -> str:
		if not retrieved:
			return (
				"> ⚠️ **No supporting records were retrieved.**\n\n"
				"Try narrowing your query:\n"
				"- Add a **source filter** — e.g. *\"in Gmail\"*, *\"from Slack\"*, *\"in Notion\"*\n"
				"- Add a **time window** — e.g. *\"last week\"*, *\"in March\"*\n"
				"- Use **exact keywords** from the content"
			)

		return (
			f"> ⚠️ **I couldn't find confident evidence** for *\"{query}\"* in your personal data.\n\n"
			"Try refining with:\n"
			"- A **source filter** — e.g. *\"in Gmail\"*, *\"from Slack\"*, *\"in Notion\"*\n"
			"- A **time window** — e.g. *\"last week\"*, *\"in March\"*\n"
			"- **Exact keywords** from the content"
		)


def _extract_link(item: RetrievedItem) -> str | None:
	metadata = item.metadata or {}
	for key in ["web_view_link", "web_link", "html_link", "external_url", "file_path"]:
		value = metadata.get(key)
		if isinstance(value, str) and value.strip():
			return value
	if isinstance(item.file_path, str) and item.file_path.strip():
		return item.file_path
	return None


def _clean_preview(value: str | None, max_len: int = 320) -> str:
	if not value:
		return ""
	cleaned = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060\uFEFF]", " ", value)
	cleaned = re.sub(r"\s+", " ", cleaned).strip()
	return cleaned[:max_len]


def _query_tokens(query: str) -> set[str]:
	parts = re.findall(r"[a-z0-9]+", query.lower())
	return set(parts)


def _compose_message_digest(query: str, retrieved: list[RetrievedItem]) -> str:
	top_items = retrieved[:5]
	source_counts = Counter(item.source for item in retrieved)
	dominant_source, dominant_count = source_counts.most_common(1)[0]

	if dominant_source == "slack":
		opening = f"I found {len(retrieved)} Slack message(s) relevant to '{query}'."
	elif dominant_source == "gmail":
		opening = f"I found {len(retrieved)} message-like result(s), mostly from Gmail ({dominant_count}/{len(retrieved)})."
	else:
		opening = f"I found {len(retrieved)} message-like result(s), mostly from {dominant_source} ({dominant_count}/{len(retrieved)})."

	lines = [opening, "Top highlights:"]
	for index, item in enumerate(top_items, start=1):
		lines.append(f"{index}. {_format_message_highlight_md(item, index)}")

	lines.append("Reply with a filter like 'last 5 from #channel' or 'only DMs' for a tighter summary.")
	return "\n".join(lines)


def _compose_message_digest_md(query: str, retrieved: list[RetrievedItem]) -> str:
	source_counts = Counter(item.source for item in retrieved)
	dominant_source = source_counts.most_common(1)[0][0]

	emoji = _SOURCE_EMOJI.get(dominant_source, "💬")
	label = _SOURCE_LABEL.get(dominant_source, dominant_source.title())

	lines: list[str] = [
		f"### {emoji} {label} Messages",
		"",
		f"Found **{len(retrieved)} message(s)** related to your query:",
		"",
	]
	for index, item in enumerate(retrieved[:5], start=1):
		lines.append(_format_message_highlight_md(item, index))

	unique_sources = [s for s, _ in source_counts.most_common()]
	source_str = " · ".join(unique_sources[:3])
	lines.extend(["", "---", f"> {len(retrieved)} messages · {source_str}"])
	lines.append("")
	lines.append("> Try *\"last 5 from #channel\"* or *\"only DMs\"* for a tighter summary.")
	return "\n".join(lines)


def _format_message_highlight(item: RetrievedItem) -> str:
	metadata = item.metadata if isinstance(item.metadata, dict) else {}
	channel_name = metadata.get("channel_name") if isinstance(metadata.get("channel_name"), str) else ""
	channel_type = metadata.get("channel_type") if isinstance(metadata.get("channel_type"), str) else ""

	snippet = _clean_preview(item.preview, max_len=160) or "No content preview."
	timestamp = item.item_date.isoformat(timespec="minutes") if item.item_date else "unknown time"

	if channel_name:
		return f"#{channel_name} ({channel_type or 'channel'}) at {timestamp}: {snippet}"
	if item.source == "slack" and channel_type == "im":
		return f"DM at {timestamp}: {snippet}"
	return f"{item.source}/{item.type} at {timestamp}: {snippet}"


def _format_message_highlight_md(item: RetrievedItem, index: int) -> str:
	meta = item.metadata if isinstance(item.metadata, dict) else {}
	channel_name = meta.get("channel_name") if isinstance(meta.get("channel_name"), str) else ""
	channel_type = meta.get("channel_type") if isinstance(meta.get("channel_type"), str) else ""
	snippet = _clean_preview(item.preview, max_len=160) or "No preview available."
	ts = item.item_date.strftime("%b %d, %H:%M") if item.item_date else "unknown time"

	if channel_name:
		header = f"**#{channel_name}** *({channel_type or 'channel'})* · {ts}"
	elif item.source == "slack" and channel_type == "im":
		header = f"**DM** · {ts}"
	else:
		header = f"**{item.source}/{item.type}** · {ts}"
	return f"{index}. {header} `[{index}]`\n   > {snippet}"


def _extract_evidence_span(item: RetrievedItem) -> str:
	candidate = _clean_preview(item.chunk_text or item.summary or item.content or item.title, max_len=240)
	if not candidate:
		return "No evidence preview available."
	sentences = re.split(r"(?<=[.!?])\s+", candidate)
	best = sentences[0].strip() if sentences else candidate
	return best if best else candidate


# ---------------------------------------------------------------------------
# Per-type Markdown formatters
# ---------------------------------------------------------------------------

def _format_track_item(item: RetrievedItem, index: int) -> str:
	title = (item.title or "Unknown Track").strip()
	meta = item.metadata if isinstance(item.metadata, dict) else {}

	artist = ""
	album = ""
	raw_artists = meta.get("artists")
	if raw_artists:
		if isinstance(raw_artists, list):
			artist = ", ".join(
				a["name"] if isinstance(a, dict) and "name" in a else str(a)
				for a in raw_artists[:2]
			)
		elif isinstance(raw_artists, str):
			artist = raw_artists
	raw_album = meta.get("album")
	if raw_album:
		album = raw_album.get("name", "") if isinstance(raw_album, dict) else str(raw_album)

	text = item.chunk_text or item.content or ""
	if not artist:
		m = re.search(r"\bby\s+([\w\s,\.&]+?)(?:\s+Album:|$)", text, re.IGNORECASE)
		if m:
			artist = m.group(1).strip()
	if not album:
		m = re.search(r"Album:\s*(.+?)(?:\s+Album:|$)", text, re.IGNORECASE)
		if m:
			album = m.group(1).strip()[:60]

	parts = [f"**{title}**"]
	if artist:
		parts.append(f"— {artist}")
	if album:
		parts.append(f"· *{album}*")
	return f"{index}. {' '.join(parts)} `[{index}]`"


def _format_repo_item(item: RetrievedItem, index: int) -> str:
	name = (item.title or "Unknown Repository").strip()
	meta = item.metadata if isinstance(item.metadata, dict) else {}
	lang = meta.get("language", "")
	description = _extract_evidence_span(item)
	if len(description) > 100:
		description = description[:97] + "..."

	line = f"{index}. **{name}**"
	if description and description.strip() != name.strip():
		line += f" — {description}"
	if lang:
		line += f" *({lang})*"
	line += f" `[{index}]`"
	return line


def _format_email_item(item: RetrievedItem, index: int) -> str:
	subject = (item.title or "No Subject").strip()
	snippet = _extract_evidence_span(item)
	if len(snippet) > 140:
		snippet = snippet[:137] + "..."
	date_str = f" · *{item.item_date.strftime('%b %d')}*" if item.item_date else ""
	return f"{index}. **{subject}**{date_str} `[{index}]`\n   > {snippet}"


def _format_doc_item(item: RetrievedItem, index: int) -> str:
	title = (item.title or "Untitled Document").strip()
	snippet = _extract_evidence_span(item)
	if len(snippet) > 120:
		snippet = snippet[:117] + "..."
	line = f"{index}. **{title}**"
	if snippet and snippet.strip() != title.strip():
		line += f" — {snippet}"
	line += f" `[{index}]`"
	return line


def _format_event_item(item: RetrievedItem, index: int) -> str:
	title = (item.title or "Untitled Event").strip()
	date_str = item.item_date.strftime("%b %d, %Y") if item.item_date else ""
	line = f"{index}. **{title}**"
	if date_str:
		line += f" · *{date_str}*"
	snippet = _extract_evidence_span(item)
	if snippet and snippet.strip() != title.strip() and len(snippet) < 100:
		line += f" — {snippet}"
	line += f" `[{index}]`"
	return line


def _format_generic_item(item: RetrievedItem, index: int) -> str:
	title = (item.title or f"{item.source}/{item.type}").strip()
	snippet = _extract_evidence_span(item)
	line = f"{index}. **{title}** (*{item.source}*)"
	if snippet and snippet.strip() != title.strip() and len(snippet) < 120:
		line += f" — {snippet}"
	line += f" `[{index}]`"
	return line

