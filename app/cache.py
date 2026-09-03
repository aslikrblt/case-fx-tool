"""In-process cache for resolved exchange rates.

Keyed by (base_currency, target_currency, date) — never by currency pair
alone, or rates asked for different dates would collide and a caller could
be served the wrong day's number. "date" here is deliberately whichever of
these is known: the date the caller asked for (or the "latest" sentinel
when none was given), and — once the upstream has answered — the date it
actually published the rate for. Both get a cache entry pointing at the
same payload, so a later request for either one is served without a second
upstream call, and a request for a date we've never resolved always goes
to the upstream (and only the upstream) to find out.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import httpx

from app.upstream import fetch_rates

_LATEST = "latest"

_cache: dict[tuple[str, str, str], dict[str, Any]] = {}


def clear() -> None:
    """Drop every cached entry. Mainly for test isolation."""
    _cache.clear()


def _key(base_currency: str, target_currency: str, on: dt.date | str) -> tuple[str, str, str]:
    marker = on if isinstance(on, str) else on.isoformat()
    return (base_currency, target_currency, marker)


async def get_rates(
    client: httpx.AsyncClient,
    base_currency: str,
    target_currency: str,
    on: dt.date | None,
) -> tuple[dict[str, Any], dt.date]:
    """Same contract as upstream.fetch_rates, backed by the cache above."""
    asked_key = _key(base_currency, target_currency, on if on is not None else _LATEST)
    cached_payload = _cache.get(asked_key)
    if cached_payload is not None:
        return cached_payload, dt.date.fromisoformat(cached_payload["date"])

    payload, rate_date = await fetch_rates(client, base_currency, target_currency, on=on)
    _cache[asked_key] = payload
    _cache[_key(base_currency, target_currency, rate_date)] = payload
    return payload, rate_date
