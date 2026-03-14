from __future__ import annotations

import atexit
import threading

import httpx


_DEFAULT_MAX_CONNECTIONS = 100
_DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 20

_client_lock = threading.Lock()
_clients: dict[tuple[float, int, int], httpx.Client] = {}


def get_http_client(
    timeout_seconds: float,
    *,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    max_keepalive_connections: int = _DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
) -> httpx.Client:
    """Return a shared sync HTTP client keyed by timeout and connection limits."""
    timeout_value = float(timeout_seconds)
    key = (timeout_value, int(max_connections), int(max_keepalive_connections))

    with _client_lock:
        existing = _clients.get(key)
        if existing is not None:
            return existing

        client = httpx.Client(
            timeout=timeout_value,
            limits=httpx.Limits(
                max_connections=int(max_connections),
                max_keepalive_connections=int(max_keepalive_connections),
            ),
        )
        _clients[key] = client
        return client


def close_http_clients() -> None:
    """Close all shared clients. Useful for clean shutdown hooks/tests."""
    with _client_lock:
        clients = list(_clients.values())
        _clients.clear()

    for client in clients:
        try:
            client.close()
        except Exception:
            pass


atexit.register(close_http_clients)
