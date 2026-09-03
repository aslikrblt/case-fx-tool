"""The in-process rate cache: a repeated (from, to, resolved date) query
must not hit the upstream a second time, and different dates must never
be cached together.
"""

from __future__ import annotations

import httpx
import pytest


class CountingHandler:
    """Wraps a Frankfurter-shaped handler and counts how often it's called."""

    def __init__(self):
        self.call_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        if request.url.path == "/v1/2026-08-28":
            return httpx.Response(
                200,
                json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 47.1234}},
            )
        if request.url.path == "/v1/2026-08-27":
            return httpx.Response(
                200,
                json={"amount": 1.0, "base": "EUR", "date": "2026-08-27", "rates": {"TRY": 46.9}},
            )
        raise AssertionError(f"unexpected upstream request path: {request.url.path}")


@pytest.fixture
def counting_handler() -> CountingHandler:
    return CountingHandler()


@pytest.fixture
def fake_upstream_handler(counting_handler: CountingHandler) -> CountingHandler:
    return counting_handler


async def test_repeated_query_hits_upstream_only_once(
    api_client: httpx.AsyncClient, counting_handler: CountingHandler
) -> None:
    params = {"amount": 250, "from": "EUR", "to": "TRY", "date": "2026-08-28"}

    first = await api_client.get("/tools/convert", params=params)
    second = await api_client.get("/tools/convert", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert counting_handler.call_count == 1


async def test_different_dates_are_never_cached_together(
    api_client: httpx.AsyncClient, counting_handler: CountingHandler
) -> None:
    first = await api_client.get(
        "/tools/convert", params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2026-08-28"}
    )
    second = await api_client.get(
        "/tools/convert", params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2026-08-27"}
    )

    assert counting_handler.call_count == 2
    assert first.json()["rate_date"] == "2026-08-28"
    assert second.json()["rate_date"] == "2026-08-27"
    assert first.json()["rate"] != second.json()["rate"]
