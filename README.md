# fx-tool

A small HTTP service an AI agent can call as a tool to convert an amount
between two currencies using ECB reference rates (via [Frankfurter](https://frankfurter.dev)).

## Run

```bash
PORT=8080 FX_UPSTREAM_BASE=https://api.frankfurter.dev ./run.sh
```

- `PORT` — port to listen on. Default `8080`.
- `FX_UPSTREAM_BASE` — upstream root URL. Default `https://api.frankfurter.dev`. Point it
  at a fake upstream to run without the real API.

```bash
curl "http://localhost:8080/tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28"
```

```json
{
  "amount": 250, "from": "EUR", "to": "TRY",
  "rate": 47.1234, "result": 11780.85,
  "rate_date": "2026-08-28", "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

`date` is optional; omit it for the latest published rate.

## Test

```bash
./test.sh
```

- Runs `pytest`.
- **Fully network-free**: the upstream is replaced with an `httpx.MockTransport`
  fake via a FastAPI dependency override (see `tests/conftest.py`), and `test.sh`
  itself defaults `FX_UPSTREAM_BASE` to a closed port so even a bare `./test.sh`
  never touches the network.

## Error codes

Every non-2xx response is `{"error": "<code>", "message": "<sentence>"}`.

| Code | HTTP status | Returned when |
|---|---|---|
| `invalid_request` | 400 | a query parameter fails basic parsing (e.g. `amount=abc`, an unparsable `date`, `from`/`to` missing entirely) |
| `amount_missing` | 400 | `amount` was not provided |
| `amount_not_positive` | 400 | `amount` is zero, negative, or not a finite number |
| `amount_too_precise` | 400 | `amount` has more than 4 decimal places |
| `unknown_currency` | 400 | `from` or `to` is not a currency Frankfurter/the ECB publishes |
| `same_currency` | 400 | `from` and `to` are the same currency |
| `date_in_future` | 400 | `date` is later than today |
| `date_before_series_start` | 400 | `date` is before `1999-01-04`, when the ECB series starts |
| `upstream_timeout` | 504 | the upstream request timed out |
| `upstream_error` | 502 | the upstream returned a non-2xx status, or was unreachable |
| `upstream_invalid_response` | 502 | the upstream's body wasn't valid JSON, or was missing the fields we need |

## Behavior by scenario

- **Weekend / public holiday** (no rate published for the asked date): the upstream's
  own fallback to the last published rate is used as-is. `rate_date` is read from
  what the upstream actually returned, `asked_date` stays what was asked — they're
  shown as two separate fields, never merged or hidden.
- **Future date**: rejected before any upstream call, `date_in_future`.
- **Date before 1999-01-04**: rejected before any upstream call, `date_before_series_start`.
- **Unknown or invalid currency code** (`from` and/or `to`): rejected before any
  upstream call, `unknown_currency`.
- **`from` equals `to`**: rejected before any upstream call, `same_currency`.
- **Upstream is slow, errors, or returns a broken body**: no rate is ever invented
  and nothing is reported as 200 — `upstream_timeout`, `upstream_error`, or
  `upstream_invalid_response`, matching what actually failed.
- **Invalid `amount`** (missing, zero, negative, or more than 4 decimal places):
  rejected before any upstream call, with the matching `amount_*` code.
- **Repeat request** for the same `(from, to, resolved date)`: served from an
  in-process cache, no second upstream call.
