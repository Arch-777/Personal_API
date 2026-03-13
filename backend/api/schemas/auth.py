import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)
	full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class GoogleLoginRequest(BaseModel):
	id_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"


class UserResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	email: EmailStr
	full_name: str | None = None
	created_at: datetime

