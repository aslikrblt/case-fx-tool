"""Tests for how /tools/convert reacts when the upstream itself misbehaves.

None of these should ever come back as a 200 with a default/zero/invented
rate — each must surface as a distinct, machine-readable error.
"""

from __future__ import annotations

import httpx
import pytest


def fake_frankfurter_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/2020-01-01":
        raise httpx.ReadTimeout("simulated upstream timeout", request=request)
    if request.url.path == "/v1/2020-01-02":
        return httpx.Response(500, text="internal server error")
    if request.url.path == "/v1/2020-01-03":
        return httpx.Response(200, text="<html>not json</html>")
    raise AssertionError(f"unexpected upstream request path: {request.url.path}")


@pytest.fixture
def fake_upstream_handler():
    return fake_frankfurter_handler


async def test_convert_reports_upstream_timeout(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2020-01-01"},
    )

    assert response.status_code == 504
    body = response.json()
    assert body["error"] == "upstream_timeout"
    assert isinstance(body["message"], str) and body["message"]


async def test_convert_reports_upstream_500(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2020-01-02"},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_error"
    assert "500" in body["message"]


async def test_convert_reports_upstream_invalid_json(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2020-01-03"},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_invalid_response"
    assert isinstance(body["message"], str) and body["message"]
