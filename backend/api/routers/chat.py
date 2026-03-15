from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.db import get_db
from api.models.chat_session import ChatMessage, ChatSession
from api.models.user import User
from api.schemas.chat import (
	ChatFeedbackRequest,
	ChatFeedbackResponse,
	ChatHistoryMessage,
	ChatMessageRequest,
	ChatMessageResponse,
	ChatSource,
)
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
	conversation_history = _recent_conversation_context(db, session.id, limit=6)

	db.add(ChatMessage(session_id=session.id, role="user", content=user_message, sources=[]))

	engine = RAGEngine(db=db, user_id=current_user.id)
	rag_result = engine.query(
		query=user_message,
		top_k=6,
		include_debug=include_debug,
		conversation_history=conversation_history,
	)

	assistant_sources = list(rag_result.get("sources", []))
	assistant_answer = str(rag_result.get("answer", ""))
	answer_mode = str(rag_result.get("answer_mode", "deterministic"))
	assistant_message = ChatMessage(
		session_id=session.id,
		role="assistant",
		content=assistant_answer,
		sources=assistant_sources,
	)

	db.add(assistant_message)

	session.updated_at = datetime.now(UTC)
	db.commit()
	db.refresh(assistant_message)

	return ChatMessageResponse(
		session_id=str(session.id),
		assistant_message_id=str(assistant_message.id),
		answer=assistant_answer,
		answer_mode=answer_mode,
		sources=[ChatSource(**source) for source in assistant_sources],
		documents=[str(item) for item in rag_result.get("documents", [])],
		file_links=[str(item) for item in rag_result.get("file_links", [])],
	)


@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_chat_feedback(
	payload: ChatFeedbackRequest,
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> ChatFeedbackResponse:
	session_id = _parse_uuid_or_400(payload.session_id, field_name="session_id")
	assistant_message_id = _parse_uuid_or_400(payload.assistant_message_id, field_name="assistant_message_id")

	session = _load_chat_session(db, current_user.id, session_id)
	assistant_message = db.execute(
		select(ChatMessage).where(
			and_(
				ChatMessage.id == assistant_message_id,
				ChatMessage.session_id == session.id,
				ChatMessage.role == "assistant",
			)
		)
	).scalar_one_or_none()
	if assistant_message is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant message not found")

	linked_user_message = db.execute(
		select(ChatMessage)
		.where(
			and_(
				ChatMessage.session_id == session.id,
				ChatMessage.role == "user",
				ChatMessage.created_at <= assistant_message.created_at,
			)
		)
		.order_by(ChatMessage.created_at.desc())
		.limit(1)
	).scalar_one_or_none()

	feedback_payload = {
		"event": "chat_feedback",
		"assistant_message_id": str(assistant_message.id),
		"linked_user_message_id": str(linked_user_message.id) if linked_user_message else None,
		"thumbs_up": bool(payload.thumbs_up),
		"note": payload.note,
		"query": linked_user_message.content if linked_user_message else None,
		"answer": assistant_message.content,
		"sources": assistant_message.sources or [],
	}

	feedback_message = ChatMessage(
		session_id=session.id,
		role="feedback",
		content=(payload.note or ("thumbs_up" if payload.thumbs_up else "thumbs_down")).strip(),
		sources=[feedback_payload],
	)
	db.add(feedback_message)
	session.updated_at = datetime.now(UTC)
	db.commit()
	db.refresh(feedback_message)

	return ChatFeedbackResponse(
		feedback_id=str(feedback_message.id),
		session_id=str(session.id),
		assistant_message_id=str(assistant_message.id),
		thumbs_up=bool(payload.thumbs_up),
	)


@router.get("/{session_id}/history", response_model=list[ChatHistoryMessage])
def get_chat_history(
	session_id: uuid.UUID,
	limit: int = Query(default=50, ge=1, le=200),
	query: str | None = Query(default=None, min_length=1, max_length=200, description="Filter messages by content text."),
	order: Literal["asc", "desc"] = Query(default="asc", description="Sort by created_at. Use desc for recent-first results."),
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> list[ChatHistoryMessage]:
	session = _load_chat_session(db, current_user.id, session_id)
	return _query_chat_history(db, session.id, limit=limit, query=query, order=order)


@router.get("/history", response_model=list[ChatHistoryMessage])
def get_recent_chat_history(
	limit: int = Query(default=50, ge=1, le=200),
	query: str | None = Query(default=None, min_length=1, max_length=200, description="Filter messages by content text."),
	order: Literal["asc", "desc"] = Query(default="asc", description="Sort by created_at. Use desc for recent-first results."),
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> list[ChatHistoryMessage]:
	latest_session = db.execute(
		select(ChatSession)
		.where(ChatSession.user_id == current_user.id)
		.order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
		.limit(1)
	).scalar_one_or_none()

	if latest_session is None:
		return []

	return _query_chat_history(db, latest_session.id, limit=limit, query=query, order=order)


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


def _load_chat_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
	session = db.execute(
		select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
	).scalar_one_or_none()
	if session is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
	return session


def _query_chat_history(
	db: Session,
	session_id: uuid.UUID,
	*,
	limit: int,
	query: str | None,
	order: Literal["asc", "desc"],
) -> list[ChatHistoryMessage]:
	search_term = query.strip() if query else None
	stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
	if search_term:
		stmt = stmt.where(ChatMessage.content.ilike(f"%{search_term}%"))

	rows = db.execute(
		stmt.order_by(ChatMessage.created_at.desc() if order == "desc" else ChatMessage.created_at.asc()).limit(limit)
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


def _recent_conversation_context(db: Session, session_id: uuid.UUID, limit: int = 6) -> list[dict[str, str]]:
	rows = db.execute(
		select(ChatMessage)
		.where(
			and_(
				ChatMessage.session_id == session_id,
				ChatMessage.role.in_(["user", "assistant"]),
			)
		)
		.order_by(ChatMessage.created_at.desc())
		.limit(max(1, min(limit, 20)))
	).scalars().all()

	history: list[dict[str, str]] = []
	for row in reversed(rows):
		content = (row.content or "").strip()
		if not content:
			continue
		history.append({"role": row.role, "content": content})
	return history


def _parse_uuid_or_400(value: str, field_name: str) -> uuid.UUID:
	try:
		return uuid.UUID(value)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field_name}") from exc

