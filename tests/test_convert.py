"""Smoke test for /tools/convert.

The endpoint is still a placeholder (see app/main.py), so this only proves
the request path works end to end — routing, param parsing, response shape
— without ever touching a real upstream, even though FX_UPSTREAM_BASE may
be pointing at a closed port when this runs.
"""

from __future__ import annotations

import httpx


async def test_convert_placeholder_responds_without_network(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/tools/convert",
        params={"amount": 250, "from": "EUR", "to": "TRY", "date": "2026-08-28"},
    )

    assert response.status_code == 501
    body = response.json()
    assert body["error"] == "not_implemented"
