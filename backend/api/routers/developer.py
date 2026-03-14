import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.db import get_db
from api.models.api_key import ApiKey
from api.models.user import User


router = APIRouter(prefix="/developer", tags=["developer"])


class ApiKeyCreateRequest(BaseModel):
	name: str | None = Field(default=None, max_length=120)
	allowed_channels: list[str] = Field(default_factory=list)
	agent_type: str | None = Field(default=None, max_length=50)
	expires_in_days: int | None = Field(default=None, ge=1, le=3650)
	expires_at: datetime | None = Field(default=None)

	@model_validator(mode="after")
	def validate_expiry_input(self):
		if self.expires_in_days is not None and self.expires_at is not None:
			raise ValueError("Provide either expires_in_days or expires_at, not both")
		return self


class ApiKeyCreateResponse(BaseModel):
	id: str
	name: str | None
	key_prefix: str
	api_key: str
	allowed_channels: list[str]
	agent_type: str | None
	created_at: datetime
	expires_at: datetime | None = None


class ApiKeyListItem(BaseModel):
	id: str
	name: str | None
	key_prefix: str
	allowed_channels: list[str]
	agent_type: str | None
	created_at: datetime
	last_used_at: datetime | None = None
	expires_at: datetime | None = None
	revoked_at: datetime | None = None


def _hash_api_key(raw_key: str) -> str:
	return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
	payload: ApiKeyCreateRequest,
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> ApiKeyCreateResponse:
	now = datetime.now(UTC)
	expires_at = payload.expires_at
	if payload.expires_in_days is not None:
		expires_at = now + timedelta(days=payload.expires_in_days)

	if expires_at is not None:
		if expires_at.tzinfo is None:
			expires_at = expires_at.replace(tzinfo=UTC)
		if expires_at <= now:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail="expires_at must be in the future",
			)

	raw_key = f"pk_live_{secrets.token_urlsafe(32)}"
	key_prefix = raw_key[:14]
	key_hash = _hash_api_key(raw_key)

	api_key = ApiKey(
		user_id=current_user.id,
		name=payload.name,
		key_prefix=key_prefix,
		key_hash=key_hash,
		allowed_channels=payload.allowed_channels,
		agent_type=payload.agent_type,
		expires_at=expires_at,
	)
	db.add(api_key)
	db.commit()
	db.refresh(api_key)

	return ApiKeyCreateResponse(
		id=str(api_key.id),
		name=api_key.name,
		key_prefix=api_key.key_prefix,
		api_key=raw_key,
		allowed_channels=api_key.allowed_channels,
		agent_type=api_key.agent_type,
		created_at=api_key.created_at,
		expires_at=api_key.expires_at,
	)


@router.get("/api-keys", response_model=list[ApiKeyListItem])
def list_api_keys(
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> list[ApiKeyListItem]:
	keys = db.execute(
		select(ApiKey)
		.where(ApiKey.user_id == current_user.id)
		.order_by(ApiKey.created_at.desc())
	).scalars().all()

	return [
		ApiKeyListItem(
			id=str(key.id),
			name=key.name,
			key_prefix=key.key_prefix,
			allowed_channels=key.allowed_channels,
			agent_type=key.agent_type,
			created_at=key.created_at,
			last_used_at=key.last_used_at,
			expires_at=key.expires_at,
			revoked_at=key.revoked_at,
		)
		for key in keys
	]


@router.post("/api-keys/{api_key_id}/revoke", response_model=ApiKeyListItem)
def revoke_api_key(
	api_key_id: str,
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> ApiKeyListItem:
	try:
		key_uuid = uuid.UUID(api_key_id)
	except ValueError:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API key id")

	api_key = db.execute(
		select(ApiKey).where(ApiKey.id == key_uuid, ApiKey.user_id == current_user.id)
	).scalar_one_or_none()
	if api_key is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

	api_key.revoked_at = datetime.now(UTC)
	db.add(api_key)
	db.commit()
	db.refresh(api_key)

	return ApiKeyListItem(
		id=str(api_key.id),
		name=api_key.name,
		key_prefix=api_key.key_prefix,
		allowed_channels=api_key.allowed_channels,
		agent_type=api_key.agent_type,
		created_at=api_key.created_at,
		last_used_at=api_key.last_used_at,
		expires_at=api_key.expires_at,
		revoked_at=api_key.revoked_at,
	)

