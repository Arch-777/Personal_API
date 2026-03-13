from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.db import get_db
from api.models.chat_session import ChatMessage, ChatSession
from api.models.user import User
from api.schemas.chat import ChatHistoryMessage, ChatMessageRequest, ChatMessageResponse, ChatSource
from rag.engine import RAGEngine


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_chat_message(
	payload: ChatMessageRequest,
	include_debug: bool = Query(default=False, description="Include score/debug breakdown in source entries."),
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
	user_message = payload.message.strip()
	if not user_message:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

	session = _load_or_create_session(db, current_user.id, payload.session_id)

	db.add(
		ChatMessage(
			session_id=session.id,
			role="user",
			content=user_message,
			sources=[],
		)
	)

	engine = RAGEngine(db=db, user_id=current_user.id)
	rag_result = engine.query(query=user_message, top_k=8, include_debug=include_debug)

	assistant_sources = list(rag_result.get("sources", []))
	assistant_answer = str(rag_result.get("answer", ""))

	db.add(
		ChatMessage(
			session_id=session.id,
			role="assistant",
			content=assistant_answer,
			sources=assistant_sources,
		)
	)

	session.updated_at = datetime.now(UTC)
	db.commit()

	return ChatMessageResponse(
		session_id=str(session.id),
		answer=assistant_answer,
		sources=[ChatSource(**source) for source in assistant_sources],
		documents=[str(item) for item in rag_result.get("documents", [])],
		file_links=[str(item) for item in rag_result.get("file_links", [])],
	)


@router.get("/{session_id}/history", response_model=list[ChatHistoryMessage])
def get_chat_history(
	session_id: uuid.UUID,
	limit: int = Query(default=50, ge=1, le=200),
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> list[ChatHistoryMessage]:
	session = db.execute(
		select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
	).scalar_one_or_none()
	if session is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

	rows = db.execute(
		select(ChatMessage)
		.where(ChatMessage.session_id == session.id)
		.order_by(ChatMessage.created_at.asc())
		.limit(limit)
	).scalars().all()

	return [
		ChatHistoryMessage(
			id=str(row.id),
			role=row.role,
			content=row.content,
			sources=row.sources or [],
			created_at=row.created_at,
		)
		for row in rows
	]


def _load_or_create_session(db: Session, user_id: uuid.UUID, session_id: str | None) -> ChatSession:
	if session_id is None:
		session = ChatSession(user_id=user_id, channel="dashboard")
		db.add(session)
		db.commit()
		db.refresh(session)
		return session

	try:
		parsed = uuid.UUID(session_id)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session_id") from exc

	session = db.execute(
		select(ChatSession).where(ChatSession.id == parsed, ChatSession.user_id == user_id)
	).scalar_one_or_none()
	if session is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
	return session

