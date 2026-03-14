from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	app_name: str = Field(default="PersonalAPI")
	app_version: str = Field(default="0.1.0")
	api_prefix: str = Field(default="/v1")
	debug: bool = Field(default=False)
	enable_inline_sync_fallback: bool = Field(default=False)

	cors_origins: str = Field(default="http://localhost:3000")
	frontend_app_url: str = Field(default="http://127.0.0.1:3000")
	user_data_root: str = Field(default="storage")

	database_url: str = Field(default="postgresql+psycopg://postgres:localpass@localhost:5432/personalapi")
	database_ssl_mode: str = Field(default="prefer")
	database_connect_timeout: int = Field(default=10)
	redis_url: str = Field(default="redis://localhost:6379/0")
	auto_sync_enabled: bool = Field(default=True)
	auto_sync_dispatch_interval_seconds: int = Field(default=300)
	auto_sync_stale_after_minutes: int = Field(default=30)
	auto_sync_batch_size: int = Field(default=25)

	rag_llm_enabled: bool = Field(default=False)
	rag_llm_provider: str = Field(default="ollama")
	rag_llm_base_url: str = Field(default="http://localhost:11434")
	rag_llm_model: str = Field(default="qwen2.5:1.5b")
	rag_llm_timeout_seconds: int = Field(default=45)
	rag_llm_temperature: float = Field(default=0.2)
	rag_llm_max_tokens: int = Field(default=512)

	secret_key: str = Field(default="change-me-in-production")
	access_token_expire_minutes: int = Field(default=60)
	algorithm: str = Field(default="HS256")
	google_client_id: str = Field(default="")
	google_allowed_client_ids: str = Field(default="")
	google_client_secret: str = Field(default="")
	google_auth_redirect_uri: str = Field(default="http://127.0.0.1:8000/auth/google/callback")
	google_redirect_uri: str = Field(default="http://127.0.0.1:8000/v1/connectors/google/callback")
	google_token_info_url: str = Field(default="https://oauth2.googleapis.com/tokeninfo")

	spotify_client_id: str = Field(default="")
	spotify_client_secret: str = Field(default="")
	spotify_redirect_uri: str = Field(default="http://127.0.0.1:8000/v1/connectors/spotify/callback")

	slack_client_id: str = Field(default="")
	slack_client_secret: str = Field(default="")
	slack_redirect_uri: str = Field(default="http://127.0.0.1:8000/v1/connectors/slack/callback")

	github_client_id: str = Field(default="")
	github_client_secret: str = Field(default="")
	github_redirect_uri: str = Field(default="http://127.0.0.1:8000/v1/connectors/github/callback")
	github_webhook_secret: str = Field(default="")

	notion_client_id: str = Field(default="")
	notion_client_secret: str = Field(default="")
	notion_redirect_uri: str = Field(default="http://127.0.0.1:8000/v1/connectors/notion/callback")

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	@property
	def cors_origin_list(self) -> list[str]:
		return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

	@property
	def google_allowed_client_id_list(self) -> list[str]:
		if self.google_allowed_client_ids.strip():
			return [client_id.strip() for client_id in self.google_allowed_client_ids.split(",") if client_id.strip()]
		if self.google_client_id.strip():
			return [self.google_client_id.strip()]
		return []


@lru_cache
def get_settings() -> Settings:
	return Settings()

