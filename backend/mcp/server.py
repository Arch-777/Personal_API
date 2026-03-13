"""MCP (Model Context Protocol) server — tool-based data access for AI agents.

Exposes user-scoped retrieval tools that external agents (Claude Desktop,
custom MCP clients, etc.) can call with a valid PersonalAPI developer key.

Run standalone:
    uvicorn mcp.server:app --port 8001

Or mount under the main app by calling ``get_mcp_app()`` and mounting at
a path such as ``/mcp``.

All tools require the ``X-API-Key`` header with a developer key issued via
``POST /v1/developer/api-keys``.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.core.db import SessionLocal
from api.models.api_key import ApiKey
from api.models.connector import Connector
from api.models.item import Item
from api.models.user import User
from rag.engine import RAGEngine


# ---------------------------------------------------------------------------
# App / mount helper
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PersonalAPI MCP Server",
    description="Tool-based access to personal data for AI agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


def get_mcp_app() -> FastAPI:
    """Return the MCP sub-application for mounting in the main FastAPI app."""
    return app


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_user(api_key_header: str) -> tuple[uuid.UUID, Session]:
    """Validate developer API key and return (user_id, db_session)."""
    raw_key = api_key_header.strip()
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    key_hash = _hash_key(raw_key)
    db = SessionLocal()
    try:
        row = db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
    except Exception:
        db.close()
        raise

    if row is None:
        db.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    # Update last_used_at
    row.last_used_at = datetime.now(UTC)
    db.commit()

    return row.user_id, db


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    type_filter: str | None = Field(default=None, description="Filter by item type: email, document, track, message, event")
    source_filter: str | None = Field(default=None, description="Filter by source: gmail, drive, notion, slack, spotify, gcal")


class SearchResultItem(BaseModel):
    id: str
    type: str
    source: str
    title: str | None
    preview: str
    score: float
    item_date: str | None
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    count: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000, description="Natural language question about your personal data")
    session_id: str | None = Field(default=None, description="Optional session ID for conversation continuity")
    top_k: int = Field(default=8, ge=1, le=30)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    documents: list[str]
    file_links: list[str]


class ItemDetailResponse(BaseModel):
    id: str
    type: str
    source: str
    source_id: str
    title: str | None
    sender_name: str | None
    sender_email: str | None
    content: str | None
    summary: str | None
    metadata: dict[str, Any]
    item_date: str | None
    file_path: str | None


class ConnectorStatusResponse(BaseModel):
    platform: str
    status: str
    platform_email: str | None
    last_synced: str | None
    error_message: str | None


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    connector_count: int
    item_count: int


# ---------------------------------------------------------------------------
# Tools / endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mcp"}


@app.post("/tools/search", response_model=SearchResponse, summary="Search personal data")
def tool_search(
    body: SearchRequest,
    x_api_key: str = Header(..., description="Developer API key (pk_live_...)"),
) -> SearchResponse:
    """Full-text + semantic search across all the user's synced personal data.

    Use this tool when an agent needs to find specific emails, documents,
    Slack messages, calendar events, or Spotify tracks.
    """
    user_id, db = _resolve_user(x_api_key)
    try:
        filters = [
            Item.user_id == user_id,
            or_(
                Item.title.ilike(f"%{body.query}%"),
                Item.content.ilike(f"%{body.query}%"),
                Item.summary.ilike(f"%{body.query}%"),
            ),
        ]
        if body.type_filter:
            filters.append(Item.type == body.type_filter)
        if body.source_filter:
            filters.append(Item.source == body.source_filter)

        rows = db.execute(
            select(Item)
            .where(*filters)
            .order_by(Item.item_date.desc().nullslast(), Item.created_at.desc())
            .limit(body.top_k)
        ).scalars().all()

        results = [
            SearchResultItem(
                id=str(row.id),
                type=row.type,
                source=row.source,
                title=row.title,
                preview=(row.summary or row.content or "")[:300],
                score=1.0,
                item_date=row.item_date.isoformat() if row.item_date else None,
                metadata=dict(row.metadata_json or {}),
            )
            for row in rows
        ]
        return SearchResponse(query=body.query, results=results, count=len(results))
    finally:
        db.close()


@app.post("/tools/ask", response_model=AskResponse, summary="Ask a question about personal data")
def tool_ask(
    body: AskRequest,
    x_api_key: str = Header(..., description="Developer API key (pk_live_...)"),
) -> AskResponse:
    """Ask a natural language question and receive a grounded answer with citations.

    The answer is generated by retrieving the most relevant items from the
    user's personal data and composing a response.  If an LLM is configured
    (RAG_LLM_ENABLED=true) the answer uses the local model; otherwise it uses
    the deterministic context-assembly fallback.
    """
    user_id, db = _resolve_user(x_api_key)
    try:
        engine = RAGEngine(db=db, user_id=user_id)
        result = engine.query(query=body.question, top_k=body.top_k)
        return AskResponse(
            answer=str(result.get("answer", "")),
            sources=list(result.get("sources", [])),
            documents=[str(d) for d in result.get("documents", [])],
            file_links=[str(f) for f in result.get("file_links", [])],
        )
    finally:
        db.close()


@app.get("/tools/item/{item_id}", response_model=ItemDetailResponse, summary="Get a single item by ID")
def tool_get_item(
    item_id: str,
    x_api_key: str = Header(..., description="Developer API key (pk_live_...)"),
) -> ItemDetailResponse:
    """Retrieve the full content and metadata of a single personal data item by UUID."""
    user_id, db = _resolve_user(x_api_key)
    try:
        try:
            parsed_id = uuid.UUID(item_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item ID format")

        item = db.execute(
            select(Item).where(Item.id == parsed_id, Item.user_id == user_id)
        ).scalar_one_or_none()

        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

        return ItemDetailResponse(
            id=str(item.id),
            type=item.type,
            source=item.source,
            source_id=item.source_id,
            title=item.title,
            sender_name=item.sender_name,
            sender_email=item.sender_email,
            content=item.content,
            summary=item.summary,
            metadata=dict(item.metadata_json or {}),
            item_date=item.item_date.isoformat() if item.item_date else None,
            file_path=item.file_path,
        )
    finally:
        db.close()


@app.get("/tools/connectors", response_model=list[ConnectorStatusResponse], summary="List connector statuses")
def tool_list_connectors(
    x_api_key: str = Header(..., description="Developer API key (pk_live_...)"),
) -> list[ConnectorStatusResponse]:
    """List all connected platforms and their sync status for the user."""
    user_id, db = _resolve_user(x_api_key)
    try:
        rows = db.execute(
            select(Connector)
            .where(Connector.user_id == user_id)
            .order_by(Connector.platform.asc())
        ).scalars().all()

        return [
            ConnectorStatusResponse(
                platform=row.platform,
                status=row.status,
                platform_email=row.platform_email,
                last_synced=row.last_synced.isoformat() if row.last_synced else None,
                error_message=row.error_message,
            )
            for row in rows
        ]
    finally:
        db.close()


@app.get("/tools/profile", response_model=UserProfileResponse, summary="Get user profile and data summary")
def tool_get_profile(
    x_api_key: str = Header(..., description="Developer API key (pk_live_...)"),
) -> UserProfileResponse:
    """Return the user's profile and a summary of their synced data."""
    user_id, db = _resolve_user(x_api_key)
    try:
        from sqlalchemy import func

        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        connector_count = db.scalar(
            select(func.count()).select_from(Connector).where(Connector.user_id == user_id)
        ) or 0
        item_count = db.scalar(
            select(func.count()).select_from(Item).where(Item.user_id == user_id)
        ) or 0

        return UserProfileResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            connector_count=int(connector_count),
            item_count=int(item_count),
        )
    finally:
        db.close()


@app.get("/tools/list", summary="List available MCP tools")
def tool_list() -> dict[str, Any]:
    """Return metadata for all available tools — useful for MCP client discovery."""
    return {
        "tools": [
            {
                "name": "search",
                "method": "POST",
                "path": "/tools/search",
                "description": "Full-text search across all synced personal data (emails, documents, messages, tracks, events).",
                "input_schema": {
                    "query": "string (required) — natural language search term",
                    "top_k": "integer (default 10, max 50)",
                    "type_filter": "string|null — email|document|track|message|event",
                    "source_filter": "string|null — gmail|drive|notion|slack|spotify|gcal",
                },
            },
            {
                "name": "ask",
                "method": "POST",
                "path": "/tools/ask",
                "description": "Ask a natural language question; returns a grounded answer with source citations.",
                "input_schema": {
                    "question": "string (required)",
                    "top_k": "integer (default 8)",
                    "session_id": "string|null",
                },
            },
            {
                "name": "get_item",
                "method": "GET",
                "path": "/tools/item/{item_id}",
                "description": "Retrieve full content and metadata for a single item by UUID.",
                "input_schema": {
                    "item_id": "UUID string (path parameter)",
                },
            },
            {
                "name": "list_connectors",
                "method": "GET",
                "path": "/tools/connectors",
                "description": "List all connected platforms and their current sync status.",
                "input_schema": {},
            },
            {
                "name": "get_profile",
                "method": "GET",
                "path": "/tools/profile",
                "description": "Return user profile and a summary of synced data counts.",
                "input_schema": {},
            },
        ]
    }
