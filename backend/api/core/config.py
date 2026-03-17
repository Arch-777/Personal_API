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
	database_pool_size: int = Field(default=10)
	database_max_overflow: int = Field(default=20)
	database_pool_timeout: int = Field(default=30)
	database_pool_recycle_seconds: int = Field(default=1800)
	database_startup_check_required: bool = Field(default=True)
	database_startup_check_retries: int = Field(default=1)
	database_startup_check_retry_delay_seconds: float = Field(default=1.5)
	redis_url: str = Field(default="redis://localhost:6379/0")
	api_rate_limit_enabled: bool = Field(default=True)
	api_rate_limit_namespace: str = Field(default="ratelimit:inbound")
	api_rate_limit_requests: int = Field(default=120)
	api_rate_limit_window_seconds: int = Field(default=60)
	connector_rate_limit_enabled: bool = Field(default=True)
	connector_rate_limit_namespace: str = Field(default="ratelimit:outbound")
	connector_rate_limit_requests: int = Field(default=120)
	connector_rate_limit_window_seconds: int = Field(default=60)
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
	rag_llm_system_prompt: str = Field(default="")
	rag_llm_failover_enabled: bool = Field(default=False)
	rag_llm_failover_provider: str = Field(default="ollama")
	rag_llm_failover_base_url: str = Field(default="")
	rag_llm_failover_model: str = Field(default="")
	rag_embedding_provider: str = Field(default="fastembed")
	rag_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
	rag_embedding_dimensions: int = Field(default=1536)
	rag_grounding_min_top_score: float = Field(default=0.55)
	rag_grounding_min_avg_score: float = Field(default=0.42)
	rag_semantic_candidate_limit: int = Field(default=120)
	rag_lexical_candidate_limit: int = Field(default=120)
	rag_rrf_k: int = Field(default=20)
	rag_rrf_semantic_weight: float = Field(default=0.65)
	rag_rrf_lexical_weight: float = Field(default=0.35)
	rag_rrf_boost: float = Field(default=2.5)
	rag_chunk_max_tokens: int = Field(default=240)
	rag_chunk_overlap_tokens: int = Field(default=40)
	rag_query_rewrite_enabled: bool = Field(default=True)
	rag_query_rewrite_max_variants: int = Field(default=3)
	rag_reranker_enabled: bool = Field(default=True)
	rag_reranker_top_n: int = Field(default=24)
	rag_reranker_weight: float = Field(default=0.35)
	rag_neighbor_chunk_enabled: bool = Field(default=True)
	rag_neighbor_chunk_window: int = Field(default=1)
	rag_context_max_tokens: int = Field(default=1200)
	rag_citation_claim_verification_enabled: bool = Field(default=True)
	rag_citation_claim_min_token_overlap: float = Field(default=0.12)
	rag_cache_enabled: bool = Field(default=True)
	rag_query_embedding_cache_ttl_seconds: int = Field(default=300)
	rag_query_embedding_cache_max_size: int = Field(default=2048)
	rag_retrieval_cache_ttl_seconds: int = Field(default=120)
	rag_retrieval_cache_max_size: int = Field(default=1024)
	rag_llm_circuit_breaker_enabled: bool = Field(default=True)
	rag_llm_circuit_breaker_failure_threshold: int = Field(default=3)
	rag_llm_circuit_breaker_cooldown_seconds: int = Field(default=60)

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

