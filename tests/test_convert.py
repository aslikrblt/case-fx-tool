"""Happy-path tests for /tools/convert.

Both scenarios use a fake upstream that answers for a normal business day
(no weekend/holiday fallback involved) — that case, and error handling in
general, are covered separately. FX_UPSTREAM_BASE may point at a closed
port when these run; the fake transport means it never matters.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest


def fake_frankfurter_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.params["base"] == "EUR"
    assert request.url.params["symbols"] == "TRY"

    if request.url.path == "/v1/2026-08-28":
        return httpx.Response(
            200,
            json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 47.1234}},
        )
    if request.url.path == "/v1/latest":
        return httpx.Response(
            200,
            json={"amount": 1.0, "base": "EUR", "date": "2026-08-31", "rates": {"TRY": 47.5}},
        )
    raise AssertionError(f"unexpected upstream request path: {request.url.path}")


@pytest.fixture
def fake_upstream_handler():
    return fake_frankfurter_handler


async def test_convert_with_date_uses_rate_published_for_that_date(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 250, "from": "EUR", "to": "TRY", "date": "2026-08-28"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "amount": 250,
        "from": "EUR",
        "to": "TRY",
        "rate": 47.1234,
        "result": 11780.85,
        "rate_date": "2026-08-28",
        "asked_date": "2026-08-28",
        "source": "ECB via frankfurter.dev",
    }


async def test_convert_without_date_uses_latest_rate_and_defaults_asked_date_to_today(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "amount": 100,
        "from": "EUR",
        "to": "TRY",
        "rate": 47.5,
        "result": 4750.0,
        "rate_date": "2026-08-31",
        "asked_date": dt.date.today().isoformat(),
        "source": "ECB via frankfurter.dev",
    }
