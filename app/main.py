"""FastAPI entrypoint for the fx conversion tool service."""

from __future__ import annotations

import datetime as dt

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="fx-tool")


@app.get("/tools/convert")
async def convert(
    amount: float,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    date: dt.date | None = Query(default=None),
) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": "Conversion logic is not implemented yet.",
        },
    )
