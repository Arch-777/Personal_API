from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class GCalNormalizer(BaseNormalizer):
	platform = "gcal"
	item_type = "event"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=self.ensure_text(record.get("id")),
			payload=record,
		)

		title = self.ensure_text(record.get("summary"))
		description = self.ensure_text(record.get("description"))
		location = self.ensure_text(record.get("location"))
		content_parts = [part for part in [description, location] if part]
		content = "\n".join(content_parts) if content_parts else None

		creator_email = self.ensure_text(get_nested(record, "creator.email"))
		creator_name = self.ensure_text(get_nested(record, "creator.displayName"))

		metadata = {
			"status": self.ensure_text(record.get("status")),
			"start": get_nested(record, "start.dateTime") or get_nested(record, "start.date"),
			"end": get_nested(record, "end.dateTime") or get_nested(record, "end.date"),
			"html_link": self.ensure_text(record.get("htmlLink")),
			"attendees_count": len(record.get("attendees", [])) if isinstance(record.get("attendees"), list) else 0,
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=title,
			sender_name=creator_name,
			sender_email=creator_email,
			content=content,
			summary=self.build_summary(content or title),
			metadata_json=metadata,
			item_date=self.coerce_datetime(
				get_nested(record, "start.dateTime")
				or get_nested(record, "start.date")
				or record.get("updated")
				or record.get("created")
			),
			raw_record=record,
		)

