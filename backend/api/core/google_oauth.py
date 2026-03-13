import httpx

from api.core.config import get_settings


settings = get_settings()

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _normalize_google_token(token: str) -> str:
	token = token.strip()
	if token.lower().startswith("bearer "):
		token = token[7:].strip()
	return token


def _extract_email(payload: dict) -> str:
	email = payload.get("email")
	email_verified = str(payload.get("email_verified", payload.get("verified_email", "false"))).lower() == "true"
	if not email or not email_verified:
		raise ValueError("Google account email is not verified")
	return str(email)


def _validate_audience(payload: dict) -> None:
	audience = str(payload.get("aud", "")).strip()
	issued_to = str(payload.get("issued_to", "")).strip()
	allowed_client_ids = set(settings.google_allowed_client_id_list)
	if not allowed_client_ids:
		raise RuntimeError("Google login is not configured. Set GOOGLE_CLIENT_ID.")
	if audience in allowed_client_ids or issued_to in allowed_client_ids:
		return
	raise ValueError("Google token audience mismatch")


def _verify_as_id_token(token: str) -> dict[str, str]:
	response = httpx.get(
		settings.google_token_info_url,
		params={"id_token": token},
		timeout=8.0,
	)
	response.raise_for_status()
	payload = response.json()

	issuer = payload.get("iss")
	if issuer not in GOOGLE_ISSUERS:
		raise ValueError("Invalid Google token issuer")

	_validate_audience(payload)
	email = _extract_email(payload)

	result: dict[str, str] = {"email": email}
	name = payload.get("name")
	if name:
		result["name"] = str(name)
	return result


def _verify_as_access_token(token: str) -> dict[str, str]:
	token_info_response = httpx.get(
		settings.google_token_info_url,
		params={"access_token": token},
		timeout=8.0,
	)
	token_info_response.raise_for_status()
	token_info_payload = token_info_response.json()
	_validate_audience(token_info_payload)

	userinfo_response = httpx.get(
		GOOGLE_USERINFO_URL,
		headers={"Authorization": f"Bearer {token}"},
		timeout=8.0,
	)
	userinfo_response.raise_for_status()
	userinfo_payload = userinfo_response.json()
	email = _extract_email(userinfo_payload)

	result: dict[str, str] = {"email": email}
	name = userinfo_payload.get("name")
	if name:
		result["name"] = str(name)
	return result


def verify_google_id_token(id_token: str) -> dict[str, str]:
	if not settings.google_allowed_client_id_list:
		raise RuntimeError("Google login is not configured. Set GOOGLE_CLIENT_ID.")
	token = _normalize_google_token(id_token)
	if not token:
		raise ValueError("Invalid Google ID token")

	try:
		return _verify_as_id_token(token)
	except httpx.HTTPError:
		# Some clients send OAuth access tokens instead of ID tokens.
		pass

	try:
		return _verify_as_access_token(token)
	except httpx.HTTPError as exc:
		raise ValueError("Invalid Google ID token") from exc
