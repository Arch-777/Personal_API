from importlib import import_module
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.core.db import check_database_connection
from api.core.config import get_settings
from rag.generator import check_ollama_readiness


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
	check_database_connection()
	yield

app = FastAPI(
	title=settings.app_name,
	version=settings.app_version,
	description="Your personal data, unified.",
	lifespan=lifespan,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origin_list,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


def include_router_if_available(module_path: str, prefix: str = "", tags: list[str] | None = None) -> None:
	module = import_module(module_path)
	router = getattr(module, "router", None)
	if router is not None:
		app.include_router(router, prefix=prefix, tags=tags)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.get("/health/llm")
def health_llm():
	current_settings = get_settings()
	provider = current_settings.rag_llm_provider.strip().lower()
	if not current_settings.rag_llm_enabled:
		return {"status": "disabled", "enabled": False, "provider": provider or "none"}

	if provider != "ollama":
		return JSONResponse(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			content={
				"status": "unsupported_provider",
				"enabled": True,
				"provider": provider or "unknown",
			},
		)

	ready, detail = check_ollama_readiness(
		base_url=current_settings.rag_llm_base_url,
		timeout_seconds=min(current_settings.rag_llm_timeout_seconds, 3),
	)
	if ready:
		return {
			"status": "ok",
			"enabled": True,
			"provider": provider,
			"base_url": current_settings.rag_llm_base_url,
			"model": current_settings.rag_llm_model,
		}

	return JSONResponse(
		status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
		content={
			"status": "unreachable",
			"enabled": True,
			"provider": provider,
			"base_url": current_settings.rag_llm_base_url,
			"model": current_settings.rag_llm_model,
			"detail": detail,
		},
	)


include_router_if_available("api.routers.auth")
include_router_if_available("api.routers.emails", prefix=settings.api_prefix)
include_router_if_available("api.routers.documents", prefix=settings.api_prefix)
include_router_if_available("api.routers.search", prefix=settings.api_prefix)
include_router_if_available("api.routers.connectors", prefix=settings.api_prefix)
include_router_if_available("api.routers.developer", prefix=settings.api_prefix)
include_router_if_available("api.routers.chat", prefix=settings.api_prefix)
include_router_if_available("api.routers.ws")

# Mount MCP sub-application
try:
	from mcp.server import get_mcp_app
	app.mount("/mcp", get_mcp_app())
except Exception as _mcp_err:  # noqa: BLE001
	import logging as _logging
	_logging.getLogger(__name__).warning("MCP server failed to load: %s", _mcp_err)

