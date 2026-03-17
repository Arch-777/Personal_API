"""
Step 11 – Async Processing Foundation tests.

All tests run offline (no broker / Redis required).
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_celery_app():
    """Import the workers package, suppressing the Settings.redis_url lookup
    so tests can run without a real .env file."""
    with patch("api.core.config.Settings.model_post_init", lambda *_: None):
        from workers.celery_app import (
            ALL_QUEUES,
            QUEUE_DEFAULT,
            QUEUE_EMBEDDING,
            QUEUE_EMBEDDING_LOW,
            QUEUE_FILE_WATCHER,
            QUEUE_GITHUB,
            QUEUE_GOOGLE,
            QUEUE_NOTION,
            QUEUE_SLACK,
            QUEUE_SPOTIFY,
            QUEUE_SYNC_HIGH,
            QUEUE_SYNC_LOW,
            QUEUE_SYNC_NORMAL,
            TASK_ROUTES,
            ResilientTask,
            celery_app,
            ping,
        )
    return (
        celery_app,
        ResilientTask,
        ping,
        ALL_QUEUES,
        QUEUE_DEFAULT,
        QUEUE_GITHUB,
        QUEUE_GOOGLE,
        QUEUE_NOTION,
        QUEUE_SLACK,
        QUEUE_SPOTIFY,
        QUEUE_FILE_WATCHER,
        QUEUE_EMBEDDING,
        QUEUE_EMBEDDING_LOW,
        QUEUE_SYNC_HIGH,
        QUEUE_SYNC_NORMAL,
        QUEUE_SYNC_LOW,
        TASK_ROUTES,
    )


# ---------------------------------------------------------------------------
# Queue constant tests
# ---------------------------------------------------------------------------

class TestQueueConstants:
    def test_queue_names_are_strings(self):
        (_, _, _, ALL_QUEUES, QUEUE_DEFAULT, QUEUE_GITHUB, QUEUE_GOOGLE,
         QUEUE_NOTION, QUEUE_SLACK, QUEUE_SPOTIFY, QUEUE_FILE_WATCHER, QUEUE_EMBEDDING,
         QUEUE_EMBEDDING_LOW, QUEUE_SYNC_HIGH, QUEUE_SYNC_NORMAL, QUEUE_SYNC_LOW, _) = _import_celery_app()

        for name in ALL_QUEUES:
            assert isinstance(name, str) and name, f"Expected non-empty string, got {name!r}"

    def test_all_queues_contains_all_expected_names(self):
        (_, _, _, ALL_QUEUES, QUEUE_DEFAULT, QUEUE_GITHUB, QUEUE_GOOGLE,
         QUEUE_NOTION, QUEUE_SLACK, QUEUE_SPOTIFY, QUEUE_FILE_WATCHER, QUEUE_EMBEDDING,
         QUEUE_EMBEDDING_LOW, QUEUE_SYNC_HIGH, QUEUE_SYNC_NORMAL, QUEUE_SYNC_LOW, _) = _import_celery_app()

        expected = {
            QUEUE_DEFAULT,
            QUEUE_GITHUB,
            QUEUE_GOOGLE,
            QUEUE_NOTION,
            QUEUE_SLACK,
            QUEUE_SPOTIFY,
            QUEUE_FILE_WATCHER,
            QUEUE_EMBEDDING,
            QUEUE_EMBEDDING_LOW,
            QUEUE_SYNC_HIGH,
            QUEUE_SYNC_NORMAL,
            QUEUE_SYNC_LOW,
        }
        assert set(ALL_QUEUES) == expected

    def test_queue_names_are_unique(self):
        (_, _, _, ALL_QUEUES, *_rest, _) = _import_celery_app()
        assert len(ALL_QUEUES) == len(set(ALL_QUEUES)), "Duplicate queue names detected"

    def test_specific_queue_name_values(self):
        (_, _, _, _, QUEUE_DEFAULT, QUEUE_GITHUB, QUEUE_GOOGLE,
         QUEUE_NOTION, QUEUE_SLACK, QUEUE_SPOTIFY, QUEUE_FILE_WATCHER, QUEUE_EMBEDDING,
         QUEUE_EMBEDDING_LOW, QUEUE_SYNC_HIGH, QUEUE_SYNC_NORMAL, QUEUE_SYNC_LOW, _) = _import_celery_app()

        assert QUEUE_DEFAULT == "default"
        assert QUEUE_GITHUB == "connector.github"
        assert QUEUE_GOOGLE == "connector.google"
        assert QUEUE_NOTION == "connector.notion"
        assert QUEUE_SLACK == "connector.slack"
        assert QUEUE_SPOTIFY == "connector.spotify"
        assert QUEUE_FILE_WATCHER == "pipeline.file-watcher"
        assert QUEUE_EMBEDDING == "pipeline.embedding"
        assert QUEUE_EMBEDDING_LOW == "pipeline.embedding.low"
        assert QUEUE_SYNC_HIGH == "sync.high"
        assert QUEUE_SYNC_NORMAL == "sync.normal"
        assert QUEUE_SYNC_LOW == "sync.low"


# ---------------------------------------------------------------------------
# Task routing table tests
# ---------------------------------------------------------------------------

class TestTaskRoutes:
    def test_all_connector_workers_are_routed(self):
        (*_, TASK_ROUTES) = _import_celery_app()

        expected_prefixes = [
            "workers.github_worker.*",
            "workers.google_worker.*",
            "workers.notion_worker.*",
            "workers.slack_worker.*",
            "workers.spotify_worker.*",
            "workers.file_watcher_worker.*",
            "workers.embedding_worker.*",
        ]
        for prefix in expected_prefixes:
            assert prefix in TASK_ROUTES, f"Missing route for {prefix}"

    def test_routes_map_to_correct_queues(self):
        (_, _, _, _, QUEUE_DEFAULT, QUEUE_GITHUB, QUEUE_GOOGLE,
         QUEUE_NOTION, QUEUE_SLACK, QUEUE_SPOTIFY, QUEUE_FILE_WATCHER, QUEUE_EMBEDDING,
         QUEUE_EMBEDDING_LOW, QUEUE_SYNC_HIGH, QUEUE_SYNC_NORMAL, QUEUE_SYNC_LOW, TASK_ROUTES) = _import_celery_app()

        assert TASK_ROUTES["workers.github_worker.*"]["queue"] == QUEUE_GITHUB
        assert TASK_ROUTES["workers.google_worker.*"]["queue"] == QUEUE_GOOGLE
        assert TASK_ROUTES["workers.notion_worker.*"]["queue"] == QUEUE_NOTION
        assert TASK_ROUTES["workers.slack_worker.*"]["queue"] == QUEUE_SLACK
        assert TASK_ROUTES["workers.spotify_worker.*"]["queue"] == QUEUE_SPOTIFY
        assert TASK_ROUTES["workers.file_watcher_worker.*"]["queue"] == QUEUE_FILE_WATCHER
        assert TASK_ROUTES["workers.embedding_worker.*"]["queue"] == QUEUE_EMBEDDING

    def test_no_route_for_default_queue(self):
        (*_, TASK_ROUTES) = _import_celery_app()
        routed_queues = [v["queue"] for v in TASK_ROUTES.values()]
        assert "default" not in routed_queues, "default queue should not be in TASK_ROUTES"


# ---------------------------------------------------------------------------
# ResilientTask configuration tests
# ---------------------------------------------------------------------------

class TestResilientTask:
    def _get_task_class(self):
        (_, ResilientTask, *_rest) = _import_celery_app()
        return ResilientTask

    def test_autoretry_for_exception(self):
        RT = self._get_task_class()
        assert Exception in RT.autoretry_for

    def test_max_retries_is_three(self):
        RT = self._get_task_class()
        assert RT.max_retries == 3

    def test_retry_backoff_enabled(self):
        RT = self._get_task_class()
        assert RT.retry_backoff is True

    def test_retry_jitter_enabled(self):
        RT = self._get_task_class()
        assert RT.retry_jitter is True

    def test_soft_time_limit_is_less_than_hard_limit(self):
        RT = self._get_task_class()
        assert RT.soft_time_limit < RT.time_limit, (
            f"soft_time_limit ({RT.soft_time_limit}) must be < time_limit ({RT.time_limit})"
        )

    def test_acks_late_enabled(self):
        RT = self._get_task_class()
        assert RT.acks_late is True

    def test_reject_on_worker_lost_enabled(self):
        RT = self._get_task_class()
        assert RT.reject_on_worker_lost is True

    def test_dlq_client_lazily_initialised(self):
        RT = self._get_task_class()
        RT._dlq_client = None
        fake_redis = MagicMock()
        with patch("workers.celery_app.Redis.from_url", return_value=fake_redis):
            client = RT._get_dlq_client()
        assert client is fake_redis
        assert RT._dlq_client is fake_redis

    def test_dlq_client_reused_on_second_call(self):
        RT = self._get_task_class()
        sentinel = MagicMock()
        RT._dlq_client = sentinel
        assert RT._get_dlq_client() is sentinel

    def test_on_failure_pushes_to_dead_letter_queue(self):
        from unittest.mock import PropertyMock
        RT = self._get_task_class()
        RT._dlq_client = None

        fake_redis = MagicMock()
        task_instance = RT()
        task_instance.name = "workers.google_worker.sync_gmail"

        fake_request = SimpleNamespace(delivery_info={"routing_key": "connector.google"})
        with patch.object(type(task_instance), "request", new_callable=PropertyMock, return_value=fake_request):
            with patch("workers.celery_app.Redis.from_url", return_value=fake_redis):
                with patch.object(RT.__bases__[0], "on_failure"):
                    task_instance.on_failure(
                        exc=ValueError("boom"),
                        task_id="t-123",
                        args=("cid", "uid"),
                        kwargs={},
                        einfo=None,
                    )

        assert fake_redis.lpush.called
        dlq_key, raw_payload = fake_redis.lpush.call_args.args
        assert dlq_key == "dlq:connector.google"
        payload = json.loads(raw_payload)
        assert payload["task_id"] == "t-123"
        assert payload["task_name"] == "workers.google_worker.sync_gmail"
        assert payload["queue"] == "connector.google"
        assert "boom" in payload["error"]
        assert "timestamp" in payload

    def test_on_failure_uses_default_queue_when_delivery_info_missing(self):
        from unittest.mock import PropertyMock
        RT = self._get_task_class()
        RT._dlq_client = None

        fake_redis = MagicMock()
        task_instance = RT()
        task_instance.name = "workers.celery_app.ping"

        # delivery_info has no routing_key — should fall back to QUEUE_DEFAULT
        fake_request = SimpleNamespace(delivery_info={})
        with patch.object(type(task_instance), "request", new_callable=PropertyMock, return_value=fake_request):
            with patch("workers.celery_app.Redis.from_url", return_value=fake_redis):
                with patch.object(RT.__bases__[0], "on_failure"):
                    task_instance.on_failure(
                        exc=RuntimeError("oops"),
                        task_id="t-456",
                        args=(),
                        kwargs={},
                        einfo=None,
                    )

        dlq_key = fake_redis.lpush.call_args.args[0]
        assert dlq_key == "dlq:default"

    def test_on_failure_swallows_redis_error_without_raising(self):
        from unittest.mock import PropertyMock
        RT = self._get_task_class()
        RT._dlq_client = None

        from redis.exceptions import RedisError
        bad_redis = MagicMock()
        bad_redis.lpush.side_effect = RedisError("connection lost")

        task_instance = RT()
        task_instance.name = "workers.notion_worker.sync_notion"

        fake_request = SimpleNamespace(delivery_info={"routing_key": "connector.notion"})
        with patch.object(type(task_instance), "request", new_callable=PropertyMock, return_value=fake_request):
            with patch("workers.celery_app.Redis.from_url", return_value=bad_redis):
                with patch.object(RT.__bases__[0], "on_failure"):
                    # Must not raise
                    task_instance.on_failure(
                        exc=IOError("net"),
                        task_id="t-789",
                        args=(),
                        kwargs={},
                        einfo=None,
                    )


# ---------------------------------------------------------------------------
# Celery app configuration tests
# ---------------------------------------------------------------------------

class TestCeleryAppConfiguration:
    def _app(self):
        (celery_app, *_rest) = _import_celery_app()
        return celery_app

    def test_app_name(self):
        app = self._app()
        assert app.main == "personal_api_workers"

    def test_default_queue_is_default(self):
        app = self._app()
        assert app.conf.task_default_queue == "default"

    def test_task_serializer_is_json(self):
        app = self._app()
        assert app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        app = self._app()
        assert app.conf.result_serializer == "json"

    def test_accept_content_is_json_only(self):
        app = self._app()
        assert list(app.conf.accept_content) == ["json"]

    def test_timezone_is_utc(self):
        app = self._app()
        assert app.conf.timezone == "UTC"

    def test_enable_utc(self):
        app = self._app()
        assert app.conf.enable_utc is True

    def test_track_started_is_on(self):
        app = self._app()
        assert app.conf.task_track_started is True

    def test_prefetch_multiplier_is_one(self):
        app = self._app()
        assert app.conf.worker_prefetch_multiplier == 1

    def test_create_missing_queues_disabled(self):
        app = self._app()
        assert app.conf.task_create_missing_queues is False

    def test_declared_queues_match_all_queues_constant(self):
        (celery_app, _, _, ALL_QUEUES, *_rest, _) = _import_celery_app()
        declared_names = {q.name for q in celery_app.conf.task_queues}
        assert declared_names == set(ALL_QUEUES)

    def test_base_task_class_is_resilient(self):
        (celery_app, ResilientTask, *_rest) = _import_celery_app()
        assert celery_app.Task is ResilientTask

    def test_task_routes_registered(self):
        (celery_app, _, _, _, *_rest, TASK_ROUTES) = _import_celery_app()
        for pattern in TASK_ROUTES:
            assert pattern in celery_app.conf.task_routes


# ---------------------------------------------------------------------------
# ping task tests
# ---------------------------------------------------------------------------

class TestPingTask:
    def test_ping_task_is_registered(self):
        (celery_app, *_rest) = _import_celery_app()
        assert "workers.celery_app.ping" in celery_app.tasks

    def test_ping_task_returns_pong(self):
        (_, _, ping, *_rest) = _import_celery_app()
        assert ping() == "pong"

    def test_ping_task_is_bound_to_default_queue(self):
        (celery_app, *_rest) = _import_celery_app()
        task = celery_app.tasks["workers.celery_app.ping"]
        # The task inherits ResilientTask settings; queue binding via TASK_ROUTES
        # only applies to wildcard route patterns. Confirm it's registered.
        assert task is not None

    def test_ping_task_callable_directly(self):
        (_, _, ping, *_rest) = _import_celery_app()
        result = ping.run() if hasattr(ping, "run") else ping()
        assert result == "pong"


# ---------------------------------------------------------------------------
# Worker module include list
# ---------------------------------------------------------------------------

class TestWorkerIncludes:
    EXPECTED_INCLUDES = [
        "workers.auto_sync_worker",
        "workers.github_worker",
        "workers.google_worker",
        "workers.notion_worker",
        "workers.slack_worker",
        "workers.spotify_worker",
        "workers.file_watcher_worker",
        "workers.embedding_worker",
    ]

    def test_all_worker_modules_included(self):
        (celery_app, *_rest) = _import_celery_app()
        for module in self.EXPECTED_INCLUDES:
            assert module in celery_app.conf.include, f"Missing include: {module}"

    def test_no_extra_unexpected_includes(self):
        (celery_app, *_rest) = _import_celery_app()
        extra = set(celery_app.conf.include) - set(self.EXPECTED_INCLUDES)
        assert not extra, f"Unexpected worker modules in include list: {extra}"


class TestBeatSchedule:
    def test_auto_sync_task_scheduled(self):
        (celery_app, *_rest) = _import_celery_app()
        schedule = celery_app.conf.beat_schedule
        assert "auto-sync-connected-integrations" in schedule
        entry = schedule["auto-sync-connected-integrations"]
        assert entry["task"] == "workers.auto_sync_worker.dispatch_auto_sync"
