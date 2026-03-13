from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
	query: str = Field(min_length=1, max_length=2000)
	top_k: int = Field(default=10, ge=1, le=50)
	type_filter: str | None = None


class SearchResult(BaseModel):
	id: str
	type: str
	source: str
	preview: str
	score: float
	metadata: dict[str, Any] = Field(default_factory=dict)
	item_date: datetime | None = None
	debug: dict[str, Any] | None = None


class SearchResponse(BaseModel):
	query: str
	results: list[SearchResult]
	count: int

