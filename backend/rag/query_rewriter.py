from __future__ import annotations

import re


_TOKEN_ALIASES = {
	"mails": "mail",
	"emails": "email",
	"msgs": "messages",
	"docs": "documents",
	"favourites": "favorites",
}

_HINT_EXPANSIONS = {
	"mail": ["gmail", "email"],
	"email": ["gmail", "inbox"],
	"gmail": ["email", "inbox"],
	"slack": ["messages", "channel"],
	"channel": ["slack", "messages"],
	"dm": ["slack", "messages"],
	"dms": ["slack", "messages"],
	"doc": ["documents", "notion", "drive"],
	"docs": ["documents", "notion", "drive"],
	"document": ["notion", "drive", "file"],
	"documents": ["notion", "drive", "file"],
	"note": ["notion", "documents"],
	"notes": ["notion", "documents"],
	"meeting": ["agenda", "notes"],
	"roadmap": ["milestones", "plan"],
}


class QueryRewriter:
	def __init__(self, enabled: bool = True, max_variants: int = 3):
		self.enabled = bool(enabled)
		self.max_variants = max(1, int(max_variants))

	def rewrite(self, query: str) -> list[str]:
		normalized = " ".join((query or "").split()).strip().lower()
		if not normalized:
			return []
		if not self.enabled:
			return [normalized]

		base_tokens = [_TOKEN_ALIASES.get(token, token) for token in _tokens(normalized)]
		if not base_tokens:
			return [normalized]

		variants: list[str] = [" ".join(base_tokens)]
		expansion_tokens: list[str] = []
		for token in base_tokens:
			expansion_tokens.extend(_HINT_EXPANSIONS.get(token, []))

		if expansion_tokens:
			variants.append(_join_deduped(base_tokens + expansion_tokens))

		if len(base_tokens) > 1:
			keywords = [token for token in base_tokens if token not in {"show", "please", "my", "me", "the", "a", "an", "for"}]
			if keywords:
				variants.append(_join_deduped(keywords + expansion_tokens))

		unique: list[str] = []
		seen: set[str] = set()
		for variant in variants:
			clean = " ".join(variant.split()).strip()
			if not clean or clean in seen:
				continue
			seen.add(clean)
			unique.append(clean)
			if len(unique) >= self.max_variants:
				break

		return unique or [normalized]


def _tokens(text: str) -> list[str]:
	return re.findall(r"[a-z0-9]+", text.lower())


def _join_deduped(tokens: list[str]) -> str:
	seen: set[str] = set()
	ordered: list[str] = []
	for token in tokens:
		if token in seen:
			continue
		seen.add(token)
		ordered.append(token)
	return " ".join(ordered)
