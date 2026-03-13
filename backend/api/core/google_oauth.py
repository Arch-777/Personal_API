import httpx

from api.core.config import get_settings


settings = get_settings()


def verify_google_id_token(id_token: str) -> dict[str, str]:
	if not settings.google_client_id:
		raise RuntimeError("Google login is not configured. Set GOOGLE_CLIENT_ID.")

	try:
		response = httpx.get(
			settings.google_token_info_url,
			params={"id_token": id_token},
			timeout=8.0,
		)
		response.raise_for_status()
	except httpx.HTTPError as exc:
		raise ValueError("Invalid Google ID token") from exc

	payload = response.json()
	issuer = payload.get("iss")
	if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
		raise ValueError("Invalid Google token issuer")

	audience = payload.get("aud")
	if audience != settings.google_client_id:
		raise ValueError("Google token audience mismatch")

	email = payload.get("email")
	email_verified = str(payload.get("email_verified", "false")).lower() == "true"
	if not email or not email_verified:
		raise ValueError("Google account email is not verified")

	result: dict[str, str] = {"email": email}
	name = payload.get("name")
	if name:
		result["name"] = name
	return result
