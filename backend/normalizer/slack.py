from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem


class SlackNormalizer(BaseNormalizer):
	platform = "slack"
	item_type = "message"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		message_ts = self.ensure_text(record.get("ts"))
		channel = record.get("_channel") if isinstance(record.get("_channel"), dict) else {}
		channel_id = self.ensure_text(channel.get("id"))
		text = self.ensure_text(record.get("text"))
		profile = record.get("_user_profile") if isinstance(record.get("_user_profile"), dict) else {}

		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=f"{channel_id}:{message_ts}" if channel_id and message_ts else None,
			payload=record,
		)
		sender_name = self.ensure_text(profile.get("display_name") or profile.get("name") or record.get("username"))
		sender_email = self.ensure_text(profile.get("email"))

		metadata = {
			"channel_id": channel_id,
			"channel_name": self.ensure_text(channel.get("name")),
			"thread_ts": self.ensure_text(record.get("thread_ts")),
			"user_id": self.ensure_text(record.get("user")),
			"message_subtype": self.ensure_text(record.get("subtype")),
			"channel_type": self._channel_type(channel),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=self.build_summary(text, max_chars=80),
			sender_name=sender_name,
			sender_email=sender_email,
			content=text,
			summary=self.build_summary(text),
			metadata_json=metadata,
			item_date=self.coerce_datetime(message_ts),
			raw_record=record,
		)

	@staticmethod
	def _channel_type(channel: dict[str, Any]) -> str | None:
		if channel.get("is_im"):
			return "im"
		if channel.get("is_mpim"):
			return "mpim"
		if channel.get("is_private"):
			return "private_channel"
		if channel:
			return "public_channel"
		return None