from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class WhatsAppNormalizer(BaseNormalizer):
	platform = "whatsapp"
	item_type = "message"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=self.ensure_text(record.get("id") or get_nested(record, "key.id") or record.get("message_id")),
			payload=record,
		)

		content = self.ensure_text(
			get_nested(record, "text.body")
			or record.get("body")
			or record.get("message")
			or get_nested(record, "interactive.body.text")
		)

		sender_name = self.ensure_text(record.get("from_name") or get_nested(record, "profile.name"))
		sender_email = None

		metadata = {
			"sender_phone": self.ensure_text(record.get("from") or record.get("author")),
			"chat_id": self.ensure_text(record.get("chat_id") or get_nested(record, "chat.id")),
			"message_type": self.ensure_text(record.get("type") or "text"),
			"context_id": self.ensure_text(get_nested(record, "context.id")),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=self.build_summary(content, max_chars=80),
			sender_name=sender_name,
			sender_email=sender_email,
			content=content,
			summary=self.build_summary(content),
			metadata_json=metadata,
			item_date=self.coerce_datetime(record.get("timestamp") or record.get("sent_at")),
			raw_record=record,
		)

