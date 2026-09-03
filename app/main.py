"""FastAPI entrypoint for the fx conversion tool service."""

from __future__ import annotations

import datetime as dt

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app.upstream import fetch_rates, get_http_client
from app.validation import ErrorCode, validate_request

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

    try:
        payload, rate_date = await fetch_rates(client, base_currency, target_currency, on=date)
        rate = payload["rates"][target_currency]
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "error": ErrorCode.UPSTREAM_TIMEOUT,
                "message": "The upstream exchange-rate service timed out. Please try again.",
            },
        )
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": ErrorCode.UPSTREAM_ERROR,
                "message": (
                    "The upstream exchange-rate service returned an error "
                    f"(HTTP {exc.response.status_code})."
                ),
            },
        )
    except (ValueError, KeyError):
        # response.json() failing (non-JSON body) is a ValueError; a JSON
        # body missing "date"/"rates" (or the target currency within it)
        # is a KeyError. Either way, the body can't be trusted.
        return JSONResponse(
            status_code=502,
            content={
                "error": ErrorCode.UPSTREAM_INVALID_RESPONSE,
                "message": "The upstream exchange-rate service returned an unreadable response.",
            },
        )
    except httpx.HTTPError:
        # Any other transport-level failure (connection refused, DNS, ...).
        return JSONResponse(
            status_code=502,
            content={
                "error": ErrorCode.UPSTREAM_ERROR,
                "message": "The upstream exchange-rate service is unavailable.",
            },
        )

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
