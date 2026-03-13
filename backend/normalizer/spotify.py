from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class SpotifyNormalizer(BaseNormalizer):
	platform = "spotify"
	item_type = "media"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		track = record.get("track") if isinstance(record.get("track"), dict) else record.get("item")
		if not isinstance(track, dict):
			track = record

		track_id = self.ensure_text(track.get("id"))
		source_id = self.deterministic_source_id(
			platform=self.platform,
			candidate_id=track_id,
			payload=record,
		)

		title = self.ensure_text(track.get("name"))
		artists = track.get("artists") if isinstance(track.get("artists"), list) else []
		artist_names = [self.ensure_text(artist.get("name")) for artist in artists if isinstance(artist, dict)]
		artist_names = [name for name in artist_names if name]
		artist_text = ", ".join(artist_names) if artist_names else None

		played_at = self.coerce_datetime(record.get("played_at") or record.get("timestamp"))
		content_parts = [part for part in [title, artist_text] if part]
		content = " by ".join(content_parts) if len(content_parts) == 2 else (content_parts[0] if content_parts else None)

		metadata = {
			"uri": self.ensure_text(track.get("uri")),
			"album": self.ensure_text(get_nested(track, "album.name")),
			"external_url": self.ensure_text(get_nested(track, "external_urls.spotify")),
			"duration_ms": track.get("duration_ms"),
			"popularity": track.get("popularity"),
		}

		return NormalizedItem(
			type=self.item_type,
			source=self.platform,
			source_id=source_id,
			title=title,
			sender_name=artist_text,
			sender_email=None,
			content=content,
			summary=self.build_summary(content),
			metadata_json=metadata,
			item_date=played_at,
			raw_record=record,
		)

