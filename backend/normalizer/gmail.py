from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class GmailNormalizer(BaseNormalizer):
	platform = "gmail"
	item_type = "email"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		header_map = self._header_map(record)

		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=self.ensure_text(record.get("id") or record.get("message_id")),
			payload=record,
		)

		subject = self.ensure_text(header_map.get("subject"))
		sender_name, sender_email = self.parse_sender(header_map.get("from"))
		snippet = self.ensure_text(record.get("snippet") or get_nested(record, "body.text"))

		metadata = {
			"thread_id": self.ensure_text(record.get("threadId") or record.get("thread_id")),
			"history_id": self.ensure_text(record.get("historyId") or record.get("history_id")),
			"label_ids": record.get("labelIds") or record.get("label_ids") or [],
			"web_link": self.ensure_text(record.get("web_link") or record.get("permalink")),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=subject,
			sender_name=sender_name,
			sender_email=sender_email,
			content=snippet,
			summary=self.build_summary(snippet),
			metadata_json=metadata,
			item_date=self.coerce_datetime(record.get("internalDate") or header_map.get("date") or record.get("date")),
			raw_record=record,
		)

	def _header_map(self, record: dict[str, Any]) -> dict[str, str]:
		result: dict[str, str] = {}
		headers = get_nested(record, "payload.headers", default=[])
		if isinstance(headers, list):
			for row in headers:
				if not isinstance(row, dict):
					continue
				name = self.ensure_text(row.get("name"))
				value = self.ensure_text(row.get("value"))
				if not name or value is None:
					continue
				result[name.lower()] = value
		return result

