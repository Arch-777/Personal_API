from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	app_name: str = Field(default="PersonalAPI")
	app_version: str = Field(default="0.1.0")
	api_prefix: str = Field(default="/v1")
	debug: bool = Field(default=False)

	cors_origins: str = Field(default="http://localhost:3000")
	user_data_root: str = Field(default="storage")

	database_url: str = Field(default="postgresql+psycopg://postgres:localpass@localhost:5432/personalapi")
	database_ssl_mode: str = Field(default="prefer")
	database_connect_timeout: int = Field(default=10)
	redis_url: str = Field(default="redis://localhost:6379/0")

	secret_key: str = Field(default="change-me-in-production")
	access_token_expire_minutes: int = Field(default=60)
	algorithm: str = Field(default="HS256")

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	@property
	def cors_origin_list(self) -> list[str]:
		return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
	return Settings()

