"""FastAPI entrypoint for the fx conversion tool service."""

from __future__ import annotations

import datetime as dt

import httpx
from fastapi import Depends, FastAPI, Query

from app.upstream import fetch_rates, get_http_client

app = FastAPI(title="fx-tool")


@app.get("/tools/convert")
async def convert(
    amount: float,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    date: dt.date | None = Query(default=None),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> dict:
    asked_date = date or dt.date.today()

    payload, rate_date = await fetch_rates(client, from_, to, on=date)
    rate = payload["rates"][to]

    return {
        "amount": amount,
        "from": from_,
        "to": to,
        "rate": rate,
        "result": round(amount * rate, 2),
        "rate_date": rate_date.isoformat(),
        "asked_date": asked_date.isoformat(),
        "source": "ECB via frankfurter.dev",
    }
