"""Validation tests for /tools/convert.

Every case here must be rejected before the upstream is ever touched, so
the fake upstream in this module raises if it's called at all — a passing
test here is also proof the request short-circuited locally.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest


def upstream_should_not_be_called(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"upstream should not be called for an invalid request, got {request.url}")


@pytest.fixture
def fake_upstream_handler():
    return upstream_should_not_be_called


async def test_convert_rejects_future_date(api_client: httpx.AsyncClient) -> None:
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY", "date": tomorrow.isoformat()},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "date_in_future",
        "message": "date cannot be in the future.",
    }


async def test_convert_rejects_date_before_series_start(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY", "date": "1999-01-03"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "date_before_series_start"
    assert "1999-01-04" in body["message"]


async def test_convert_rejects_unknown_currency_code(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "ZZZ", "to": "TRY"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unknown_currency"
    assert "ZZZ" in body["message"]


async def test_convert_rejects_same_currency(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "EUR"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "same_currency",
        "message": "'from' and 'to' must be different currencies.",
    }


async def test_convert_rejects_missing_amount(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"from": "EUR", "to": "TRY"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "amount_missing",
        "message": "amount is required.",
    }


@pytest.mark.parametrize("amount", [0, -50])
async def test_convert_rejects_non_positive_amount(api_client: httpx.AsyncClient, amount: int) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": amount, "from": "EUR", "to": "TRY"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "amount_not_positive",
        "message": "amount must be a positive number.",
    }


async def test_convert_rejects_amount_with_too_many_decimal_places(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": "250.1234567891", "from": "EUR", "to": "TRY"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "amount_too_precise",
        "message": "amount may have at most 4 decimal places.",
    }
