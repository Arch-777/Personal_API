from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any, Iterable


@dataclass(slots=True)
class NormalizedItem:
	type: str
	source: str
	source_id: str
	title: str | None
	sender_name: str | None
	sender_email: str | None
	content: str | None
	summary: str | None
	metadata_json: dict[str, Any]
	item_date: datetime | None
	raw_record: dict[str, Any]


class BaseNormalizer(ABC):
	platform: str
	item_type: str

	def normalize_records(self, records: Iterable[dict[str, Any]]) -> list[NormalizedItem]:
		normalized: list[NormalizedItem] = []
		for record in records:
			item = self.normalize_record(record)
			if item is not None:
				normalized.append(item)
		return normalized

	@abstractmethod
	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		raise NotImplementedError

	@staticmethod
	def ensure_text(value: Any) -> str | None:
		if value is None:
			return None
		if isinstance(value, str):
			stripped = value.strip()
			return stripped or None
		return str(value).strip() or None

	@staticmethod
	def build_summary(text: str | None, max_chars: int = 180) -> str | None:
		if not text:
			return None
		cleaned = " ".join(text.split())
		if len(cleaned) <= max_chars:
			return cleaned
		return f"{cleaned[: max_chars - 3]}..."

	@staticmethod
	def coerce_datetime(value: Any) -> datetime | None:
		if value is None or value == "":
			return None
		if isinstance(value, datetime):
			if value.tzinfo is None:
				return value.replace(tzinfo=UTC)
			return value.astimezone(UTC)
		if isinstance(value, (int, float)):
			timestamp = float(value)
			if timestamp > 10_000_000_000:
				timestamp /= 1000.0
			return datetime.fromtimestamp(timestamp, tz=UTC)
		if isinstance(value, str):
			candidate = value.strip()
			if not candidate:
				return None
			if candidate.isdigit():
				return BaseNormalizer.coerce_datetime(int(candidate))
			normalized = candidate.replace("Z", "+00:00")
			try:
				parsed = datetime.fromisoformat(normalized)
			except ValueError:
				return None
			if parsed.tzinfo is None:
				return parsed.replace(tzinfo=UTC)
			return parsed.astimezone(UTC)
		return None

	@staticmethod
	def parse_sender(raw_value: str | None) -> tuple[str | None, str | None]:
		text = BaseNormalizer.ensure_text(raw_value)
		if text is None:
			return None, None
		name, email = parseaddr(text)
		parsed_name = name.strip() if name else None
		parsed_email = email.strip() if email else None
		if parsed_email == "":
			parsed_email = None
		return parsed_name, parsed_email

	@staticmethod
	def deterministic_source_id(
		platform: str,
		candidate_id: str | None,
		payload: dict[str, Any],
	) -> str:
		if candidate_id:
			return candidate_id
		serialized = json.dumps(payload, sort_keys=True, default=str)
		digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
		return f"{platform}:{digest}"


def get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
	current: Any = data
	for key in path.split("."):
		if not isinstance(current, dict):
			return default
		if key not in current:
			return default
		current = current[key]
	return current

