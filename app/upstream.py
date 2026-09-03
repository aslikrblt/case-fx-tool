"""Client for the Frankfurter upstream exchange-rate API.

The HTTP client is injected rather than constructed inside `fetch_rates`, so
tests can pass a client backed by a fake transport and never touch the
network. `get_http_client` is the default FastAPI dependency for wiring a
real client into the endpoint later.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, AsyncIterator

import httpx

from app.config import FX_UPSTREAM_BASE


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """FastAPI dependency yielding a client pointed at FX_UPSTREAM_BASE."""
    async with httpx.AsyncClient(base_url=FX_UPSTREAM_BASE, timeout=10.0) as client:
        yield client


async def fetch_rates(
    client: httpx.AsyncClient,
    base_currency: str,
    target_currency: str,
    on: dt.date | None = None,
) -> tuple[dict[str, Any], dt.date]:
    """Ask the upstream for rates from `base_currency` to `target_currency`.

    `client` must be an httpx.AsyncClient whose base_url is the upstream
    root (that's what `get_http_client` sets up) — this function only ever
    requests relative paths, so a test can point the same client at a fake
    transport instead.

    Returns the upstream's raw JSON payload together with the date it
    actually published the rate for, which the payload's own "date" field
    names and which may differ from `on` (weekends/holidays fall back to
    the last published date, and the upstream is the one deciding that,
    not us). Raises on a non-2xx response or a body that isn't JSON —
    callers decide how to turn that into a customer-facing error.
    """
    path = on.isoformat() if on else "latest"
    response = await client.get(
        f"/v1/{path}",
        params={"base": base_currency, "symbols": target_currency},
    )
    response.raise_for_status()
    payload = response.json()
    rate_date = dt.date.fromisoformat(payload["date"])
    return payload, rate_date
