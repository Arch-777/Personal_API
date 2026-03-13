import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.auth import get_current_user
from api.core.config import get_settings
from api.core.db import get_db
from api.core.google_oauth import verify_google_id_token
from api.core.security import create_access_token, hash_password, verify_password
from api.models.user import User
from api.schemas.auth import GoogleLoginRequest, LoginRequest, RegisterRequest, TokenResponse, UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/connect")
def google_auth_connect() -> dict[str, str]:
	settings = get_settings()
	if not settings.google_client_id or not settings.google_client_secret:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google login is not configured")

	state = create_access_token("google-auth", expires_minutes=10)
	params = {
		"client_id": settings.google_client_id,
		"redirect_uri": settings.google_auth_redirect_uri,
		"response_type": "code",
		"scope": "openid email profile",
		"access_type": "offline",
		"prompt": "consent",
		"state": state,
	}
	return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"}


@router.get("/google/callback", response_model=TokenResponse)
def google_auth_callback(code: str, state: str, db: Session = Depends(get_db)) -> TokenResponse:
	settings = get_settings()
	if not settings.google_client_id or not settings.google_client_secret:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google login is not configured")

	try:
		payload = verify_google_oauth_state(state)
		if payload.get("sub") != "google-auth":
			raise ValueError("Invalid state subject")
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter") from exc

	try:
		with httpx.Client(timeout=15.0) as client:
			token_resp = client.post(
				"https://oauth2.googleapis.com/token",
				data={
					"client_id": settings.google_client_id,
					"client_secret": settings.google_client_secret,
					"code": code,
					"grant_type": "authorization_code",
					"redirect_uri": settings.google_auth_redirect_uri,
				},
				headers={"Content-Type": "application/x-www-form-urlencoded"},
			)
			token_resp.raise_for_status()
			token_data = token_resp.json()
	except httpx.HTTPError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Google auth code") from exc

	id_token = token_data.get("id_token")
	if not id_token:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token response missing id_token")

	try:
		google_identity = verify_google_id_token(id_token)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

	email = google_identity["email"].strip().lower()
	full_name = google_identity.get("name")

	user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
	if user is None:
		user = User(
			email=email,
			full_name=full_name,
			hashed_password=hash_password(secrets.token_urlsafe(32)),
		)
		db.add(user)
		db.commit()
		db.refresh(user)
	elif not user.full_name and full_name:
		user.full_name = full_name
		db.commit()
		db.refresh(user)

	access_token = create_access_token(str(user.id))
	return TokenResponse(access_token=access_token)


def verify_google_oauth_state(state: str) -> dict:
	from api.core.security import decode_access_token

	return decode_access_token(state)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
	existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
	if existing:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	user = User(
		email=payload.email,
		full_name=payload.full_name,
		hashed_password=hash_password(payload.password),
	)
	db.add(user)
	db.commit()
	db.refresh(user)
	return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
	user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
	if user is None or not verify_password(payload.password, user.hashed_password):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

	access_token = create_access_token(str(user.id))
	return TokenResponse(access_token=access_token)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
	try:
		google_identity = verify_google_id_token(payload.id_token)
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

	email = google_identity["email"].strip().lower()
	full_name = google_identity.get("name")

	user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
	if user is None:
		# OAuth-only accounts do not start with a local password, but schema requires a hashed value.
		user = User(
			email=email,
			full_name=full_name,
			hashed_password=hash_password(secrets.token_urlsafe(32)),
		)
		db.add(user)
		db.commit()
		db.refresh(user)
	elif not user.full_name and full_name:
		user.full_name = full_name
		db.commit()
		db.refresh(user)

	access_token = create_access_token(str(user.id))
	return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
	return UserResponse.model_validate(current_user)

