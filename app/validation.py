"""Request-input validation for /tools/convert.

Runs before the upstream is ever called, so a bad request never spends a
network round trip (or a cache slot) on something we could already tell was
wrong. Every rejection maps onto the service's error schema —
{"error": "<code>", "message": "<sentence>"} — and every code the endpoint
can return is collected in ErrorCode so there is exactly one place to look.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

# The ECB reference-rate series (and so Frankfurter's data) starts here;
# nothing earlier has ever been published.
SERIES_START_DATE = dt.date(1999, 1, 4)

# The currencies Frankfurter/the ECB publish reference rates for.
SUPPORTED_CURRENCIES = frozenset(
    {
        "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD",
        "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR", "NOK",
        "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR",
    }
)

# A currency amount with more decimal places than this is almost certainly
# a mistake (e.g. a raw float artifact), not a real sum someone wants
# converted.
MAX_AMOUNT_DECIMAL_PLACES = 4


class ErrorCode:
    """Every machine-readable error code /tools/convert can return."""

    DATE_IN_FUTURE = "date_in_future"
    DATE_BEFORE_SERIES_START = "date_before_series_start"
    UNKNOWN_CURRENCY = "unknown_currency"
    SAME_CURRENCY = "same_currency"
    AMOUNT_MISSING = "amount_missing"
    AMOUNT_NOT_POSITIVE = "amount_not_positive"
    AMOUNT_TOO_PRECISE = "amount_too_precise"


@dataclass(frozen=True)
class ValidationError:
    status_code: int
    code: str
    message: str


def validate_request(
    amount: float | None,
    raw_amount: str | None,
    base_currency: str,
    target_currency: str,
    asked_date: dt.date | None,
) -> ValidationError | None:
    """Check one /tools/convert request; return the first problem found, or None.

    `raw_amount` is the query string's own "amount" text (not the float
    FastAPI already parsed), needed to count decimal places precisely —
    float round-tripping isn't trustworthy for that.
    """
    if amount is None:
        return ValidationError(400, ErrorCode.AMOUNT_MISSING, "amount is required.")
    if not math.isfinite(amount) or amount <= 0:
        return ValidationError(400, ErrorCode.AMOUNT_NOT_POSITIVE, "amount must be a positive number.")
    if _decimal_places(raw_amount) > MAX_AMOUNT_DECIMAL_PLACES:
        return ValidationError(
            400,
            ErrorCode.AMOUNT_TOO_PRECISE,
            f"amount may have at most {MAX_AMOUNT_DECIMAL_PLACES} decimal places.",
        )

    base = base_currency.upper()
    target = target_currency.upper()
    if base not in SUPPORTED_CURRENCIES:
        return ValidationError(
            400, ErrorCode.UNKNOWN_CURRENCY, f"'{base_currency}' is not a known currency code."
        )
    if target not in SUPPORTED_CURRENCIES:
        return ValidationError(
            400, ErrorCode.UNKNOWN_CURRENCY, f"'{target_currency}' is not a known currency code."
        )
    if base == target:
        return ValidationError(400, ErrorCode.SAME_CURRENCY, "'from' and 'to' must be different currencies.")

    if asked_date is not None:
        if asked_date > dt.date.today():
            return ValidationError(400, ErrorCode.DATE_IN_FUTURE, "date cannot be in the future.")
        if asked_date < SERIES_START_DATE:
            return ValidationError(
                400,
                ErrorCode.DATE_BEFORE_SERIES_START,
                f"date cannot be before {SERIES_START_DATE.isoformat()}, when the rate series starts.",
            )

    return None


def _decimal_places(raw_amount: str | None) -> int:
    if raw_amount is None or "." not in raw_amount:
        return 0
    return len(raw_amount.rsplit(".", 1)[-1])
