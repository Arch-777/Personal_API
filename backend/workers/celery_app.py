from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery, Task
from kombu import Queue
from redis import Redis
from redis.exceptions import RedisError

from api.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

QUEUE_DEFAULT = "default"
QUEUE_GOOGLE = "connector.google"
QUEUE_WHATSAPP = "connector.whatsapp"
QUEUE_NOTION = "connector.notion"
QUEUE_SPOTIFY = "connector.spotify"
QUEUE_SLACK = "connector.slack"
QUEUE_FILE_WATCHER = "pipeline.file-watcher"
QUEUE_EMBEDDING = "pipeline.embedding"

ALL_QUEUES = (
    QUEUE_DEFAULT,
    QUEUE_GOOGLE,
    QUEUE_WHATSAPP,
    QUEUE_NOTION,
    QUEUE_SPOTIFY,
    QUEUE_SLACK,
    QUEUE_FILE_WATCHER,
    QUEUE_EMBEDDING,
)

TASK_ROUTES = {
    "workers.google_worker.*": {"queue": QUEUE_GOOGLE},
    "workers.whatsapp_worker.*": {"queue": QUEUE_WHATSAPP},
    "workers.notion_worker.*": {"queue": QUEUE_NOTION},
    "workers.spotify_worker.*": {"queue": QUEUE_SPOTIFY},
    "workers.slack_worker.*": {"queue": QUEUE_SLACK},
    "workers.file_watcher_worker.*": {"queue": QUEUE_FILE_WATCHER},
    "workers.embedding_worker.*": {"queue": QUEUE_EMBEDDING},
}


class ResilientTask(Task):
    """Base task with retry defaults and dead-letter fallback for failed jobs."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    max_retries = 3
    soft_time_limit = 240
    time_limit = 300
    acks_late = True
    reject_on_worker_lost = True

    _dlq_client: Redis | None = None

    @classmethod
    def _get_dlq_client(cls) -> Redis:
        if cls._dlq_client is None:
            cls._dlq_client = Redis.from_url(settings.redis_url, decode_responses=True)
        return cls._dlq_client

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        super().on_failure(exc, task_id, args, kwargs, einfo)

        queue_name = self.request.delivery_info.get("routing_key", QUEUE_DEFAULT)
        payload = {
            "task_id": task_id,
            "task_name": self.name,
            "queue": queue_name,
            "args": list(args),
            "kwargs": kwargs,
            "error": repr(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            dlq_key = f"dlq:{queue_name}"
            self._get_dlq_client().lpush(dlq_key, json.dumps(payload, default=str))
        except RedisError:
            logger.exception("Unable to push failed task into dead-letter queue")


celery_app = Celery(
    "personal_api_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.google_worker",
        "workers.whatsapp_worker",
        "workers.notion_worker",
        "workers.spotify_worker",
        "workers.slack_worker",
        "workers.file_watcher_worker",
        "workers.embedding_worker",
    ],
)

celery_app.conf.update(
    task_default_queue=QUEUE_DEFAULT,
    task_default_exchange=QUEUE_DEFAULT,
    task_default_routing_key=QUEUE_DEFAULT,
    task_queues=[Queue(queue_name) for queue_name in ALL_QUEUES],
    task_routes=TASK_ROUTES,
    task_create_missing_queues=False,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.Task = ResilientTask


@celery_app.task(name="workers.celery_app.ping", queue=QUEUE_DEFAULT)
def ping() -> str:
    return "pong"
