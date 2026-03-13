from __future__ import annotations

from typing import Any

from normalizer.base import BaseNormalizer, NormalizedItem, get_nested


class SpotifyNormalizer(BaseNormalizer):
	platform = "spotify"
	item_type = "track"

	def normalize_record(self, record: dict[str, Any]) -> NormalizedItem | None:
		record_type = record.get("_record_type", "recently_played")
		if record_type == "liked":
			return self._normalize_liked(record)
		return self._normalize_recently_played(record)

	def _normalize_recently_played(self, record: dict[str, Any]) -> NormalizedItem | None:
		track = record.get("track") if isinstance(record.get("track"), dict) else record.get("item")
		if not isinstance(track, dict):
			track = record

		track_id = self.ensure_text(track.get("id"))
		played_at_raw = record.get("played_at") or record.get("timestamp")
		# Include played_at in source_id so the same track played multiple times creates distinct rows.
		played_at_str = self.ensure_text(played_at_raw) or ""
		source_id = f"play:{track_id}:{played_at_str}" if track_id else self.deterministic_source_id(
			platform=self.platform, candidate_id=None, payload=record
		)

		title, artist_text, content, metadata = self._extract_track_fields(track)
		metadata["play_type"] = "recently_played"
		context = record.get("context")
		if isinstance(context, dict):
			metadata["context_type"] = context.get("type")

		played_at = self.coerce_datetime(played_at_raw)
		metadata["track_name"] = title
		metadata["artist_names"] = metadata.get("artists") if isinstance(metadata.get("artists"), list) else []
		metadata["play_count"] = record.get("play_count") or track.get("play_count")
		metadata["top_rank"] = record.get("top_rank") or record.get("rank") or track.get("top_rank")
		metadata["liked"] = bool(
			record.get("liked") or track.get("liked") or record.get("is_favorite") or record.get("is_saved")
		)
		metadata["playlist_names"] = record.get("playlist_names") if isinstance(record.get("playlist_names"), list) else []
		metadata["played_at"] = played_at.isoformat() if played_at else None

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
			item_date=self.coerce_datetime(played_at_raw),
			raw_record=record,
		)

	def _normalize_liked(self, record: dict[str, Any]) -> NormalizedItem | None:
		track = record.get("track") if isinstance(record.get("track"), dict) else record.get("item")
		if not isinstance(track, dict):
			return None

		track_id = self.ensure_text(track.get("id"))
		if not track_id:
			return None

		source_id = f"liked:{track_id}"
		added_at_raw = record.get("added_at")
		title, artist_text, content, metadata = self._extract_track_fields(track)
		metadata["play_type"] = "liked"

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
			item_date=self.coerce_datetime(added_at_raw),
			raw_record=record,
		)

	def _extract_track_fields(
		self, track: dict[str, Any]
	) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
		artists_raw = track.get("artists") if isinstance(track.get("artists"), list) else []
		artist_names = [self.ensure_text(a.get("name")) for a in artists_raw if isinstance(a, dict)]
		artist_names = [n for n in artist_names if n]
		artist_text = ", ".join(artist_names) if artist_names else None

		title = self.ensure_text(track.get("name"))
		album = self.ensure_text(get_nested(track, "album.name"))
		content_parts = [p for p in [title, artist_text] if p]
		content = " by ".join(content_parts) if len(content_parts) == 2 else (content_parts[0] if content_parts else None)
		if album:
			content = f"{content}\nAlbum: {album}" if content else f"Album: {album}"

		metadata: dict[str, Any] = {
			"track_id": self.ensure_text(track.get("id")),
			"uri": self.ensure_text(track.get("uri")),
			"album": album,
			"artists": artist_names,
			"external_url": self.ensure_text(get_nested(track, "external_urls.spotify")),
			"duration_ms": track.get("duration_ms"),
			"popularity": track.get("popularity"),
			"preview_url": self.ensure_text(track.get("preview_url")),
		}
		return title, artist_text, content, metadata

