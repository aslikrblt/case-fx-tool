"""FastAPI entrypoint for the fx conversion tool service."""

from __future__ import annotations

import datetime as dt

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app.upstream import fetch_rates, get_http_client
from app.validation import validate_request

app = FastAPI(title="fx-tool")


@app.get("/tools/convert")
async def convert(
    request: Request,
    amount: float | None = Query(default=None),
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    date: dt.date | None = Query(default=None),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> dict:
    error = validate_request(
        amount=amount,
        raw_amount=request.query_params.get("amount"),
        base_currency=from_,
        target_currency=to,
        asked_date=date,
    )
    if error is not None:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": error.code, "message": error.message},
        )

    base_currency = from_.upper()
    target_currency = to.upper()
    asked_date = date or dt.date.today()

    payload, rate_date = await fetch_rates(client, base_currency, target_currency, on=date)
    rate = payload["rates"][target_currency]

    return {
        "amount": amount,
        "from": base_currency,
        "to": target_currency,
        "rate": rate,
        "result": round(amount * rate, 2),
        "rate_date": rate_date.isoformat(),
        "asked_date": asked_date.isoformat(),
        "source": "ECB via frankfurter.dev",
    }
