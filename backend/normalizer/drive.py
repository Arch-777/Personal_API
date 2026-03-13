from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem


class DriveNormalizer(BaseNormalizer):
	platform = "drive"
	item_type = "document"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=self.ensure_text(record.get("id") or record.get("fileId")),
			payload=record,
		)

		title = self.ensure_text(record.get("name") or record.get("title"))
		description = self.ensure_text(record.get("description"))
		extracted_text = self.ensure_text(record.get("text") or record.get("textContent") or record.get("content"))
		content = extracted_text or description

		owners = record.get("owners") if isinstance(record.get("owners"), list) else []
		owner = owners[0] if owners else {}

		metadata = {
			"mime_type": self.ensure_text(record.get("mimeType") or record.get("mime_type")),
			"web_view_link": self.ensure_text(record.get("webViewLink") or record.get("alternateLink")),
			"owner_email": self.ensure_text(owner.get("emailAddress") if isinstance(owner, dict) else None),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=title,
			sender_name=self.ensure_text(owner.get("displayName") if isinstance(owner, dict) else None),
			sender_email=self.ensure_text(owner.get("emailAddress") if isinstance(owner, dict) else None),
			content=content,
			summary=self.build_summary(content or title),
			metadata_json=metadata,
			item_date=self.coerce_datetime(record.get("modifiedTime") or record.get("createdTime")),
			raw_record=record,
		)

