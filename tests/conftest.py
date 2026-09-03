"""Shared test fixtures.

`api_client` gives tests an httpx client talking to the FastAPI app
in-process (ASGI transport, no socket involved), with the real upstream
dependency swapped out for a fake httpx.MockTransport client via FastAPI's
dependency override mechanism. Nothing here ever reaches the network, so
these tests pass even when FX_UPSTREAM_BASE points at a closed port.
"""

from __future__ import annotations

from typing import AsyncIterator, Callable

import httpx
import pytest

from app import cache
from app.main import app
from app.upstream import get_http_client


@pytest.fixture(autouse=True)
def clear_rate_cache():
    """Every test starts with an empty cache — it's process-global state."""
    cache.clear()
    yield
    cache.clear()


def default_fake_upstream_handler(request: httpx.Request) -> httpx.Response:
    """A Frankfurter-shaped response; override via `fake_upstream_handler`."""
    return httpx.Response(
        200,
        json={
            "amount": 1.0,
            "base": "EUR",
            "date": "2026-08-28",
            "rates": {"TRY": 47.1234},
        },
    )


@pytest.fixture
def fake_upstream_handler() -> Callable[[httpx.Request], httpx.Response]:
    """Override this fixture in a test to control what the fake upstream returns."""
    return default_fake_upstream_handler


@pytest.fixture
async def fake_upstream_client(
    fake_upstream_handler: Callable[[httpx.Request], httpx.Response],
) -> AsyncIterator[httpx.AsyncClient]:
    """An AsyncClient wired to a MockTransport — no real socket is ever opened."""
    transport = httpx.MockTransport(fake_upstream_handler)
    async with httpx.AsyncClient(base_url="http://fake-upstream.invalid", transport=transport) as client:
        yield client


@pytest.fixture
async def api_client(fake_upstream_client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    """Client for the app itself, with the upstream dependency faked out."""

    async def _get_fake_client() -> AsyncIterator[httpx.AsyncClient]:
        yield fake_upstream_client

    app.dependency_overrides[get_http_client] = _get_fake_client
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
