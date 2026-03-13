from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class NotionNormalizer(BaseNormalizer):
	platform = "notion"
	item_type = "document"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=self.ensure_text(record.get("id") or record.get("page_id")),
			payload=record,
		)

		title = self._extract_title(record)
		content = self.ensure_text(record.get("plain_text") or record.get("excerpt") or record.get("content"))

		metadata = {
			"url": self.ensure_text(record.get("url")),
			"parent": record.get("parent") if isinstance(record.get("parent"), dict) else None,
			"archived": bool(record.get("archived", False)),
			"last_edited_time": self.ensure_text(record.get("last_edited_time")),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=title,
			sender_name=None,
			sender_email=None,
			content=content,
			summary=self.build_summary(content or title),
			metadata_json=metadata,
			item_date=self.coerce_datetime(record.get("last_edited_time") or record.get("created_time")),
			raw_record=record,
		)

	def _extract_title(self, record: dict[str, Any]) -> str | None:
		direct = self.ensure_text(record.get("title"))
		if direct:
			return direct

		properties = record.get("properties") if isinstance(record.get("properties"), dict) else {}
		for value in properties.values():
			if not isinstance(value, dict):
				continue
			if value.get("type") == "title":
				blocks = value.get("title") if isinstance(value.get("title"), list) else []
				text_chunks: list[str] = []
				for block in blocks:
					if not isinstance(block, dict):
						continue
					plain = self.ensure_text(block.get("plain_text") or get_nested(block, "text.content"))
					if plain:
						text_chunks.append(plain)
				if text_chunks:
					return " ".join(text_chunks)
		return None

