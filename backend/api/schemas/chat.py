from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
	message: str = Field(min_length=1, max_length=8000)
	session_id: str | None = None


class ChatSource(BaseModel):
	id: str
	type: str
	source: str
	score: float
	preview: str
	debug: dict[str, Any] | None = None


class ChatMessageResponse(BaseModel):
	session_id: str
	answer: str
	sources: list[ChatSource] = Field(default_factory=list)
	documents: list[str] = Field(default_factory=list)
	file_links: list[str] = Field(default_factory=list)


class ChatHistoryMessage(BaseModel):
	id: str
	role: str
	content: str
	sources: list[dict[str, Any]] = Field(default_factory=list)
	created_at: datetime

