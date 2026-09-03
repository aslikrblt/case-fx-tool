# fx-tool

A small HTTP service meant to be called as a tool by an AI agent — for example,
when a customer asks something like "how much is 250 EUR in TRY". It exposes a
single endpoint, `GET /tools/convert`, which converts an amount between two
currencies using official European Central Bank reference rates, retrieved from
the [Frankfurter](https://frankfurter.dev) API (no key or signup required).

The service is intentionally narrow: no auth, no database, no UI — one endpoint
that answers reliably, including for the historical/weekend/holiday/error edge
cases covered in [Behavior by scenario](#behavior-by-scenario) below.

## Run

`run.sh` starts the service with Uvicorn, listening on `$PORT`:

```bash
PORT=8080 FX_UPSTREAM_BASE=https://api.frankfurter.dev ./run.sh
```

- `PORT` — the port the server listens on. Defaults to `8080` if not set.
- `FX_UPSTREAM_BASE` — the root URL of the upstream exchange-rate API the
  service talks to. Defaults to the real Frankfurter API. Point it at a
  different host (e.g. a local stand-in) to run against a fake upstream
  instead of the real one — nothing in the code hardcodes the real host, so
  this always takes effect.

Once it's running, call the endpoint directly:

```bash
curl "http://localhost:8080/tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28"
```

which returns:

```json
{
  "amount": 250, "from": "EUR", "to": "TRY",
  "rate": 47.1234, "result": 11780.85,
  "rate_date": "2026-08-28", "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

`date` is optional; omit it for the latest published rate. `rate_date` is the
date the returned rate actually belongs to, as reported by the upstream;
`asked_date` is what was requested — they can differ, see
[Behavior by scenario](#behavior-by-scenario).

## Test

```bash
./test.sh
```

Runs the full `pytest` suite. The suite is **fully network-free**:
`tests/conftest.py` replaces the real upstream HTTP client with a fake one
backed by `httpx.MockTransport`, wired in through a FastAPI dependency
override, so no test ever makes a real network call. `test.sh` itself also
defaults `FX_UPSTREAM_BASE` to a closed port before running, so even a bare
`./test.sh` with no environment configured can't accidentally reach the real
API.

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

| Scenario | Status | What happens |
|---|---|---|
| Weekend / public holiday — no rate published for the asked date | 200 | The upstream's own fallback to the last published rate is used as-is. `rate_date` reflects what the upstream actually returned; `asked_date` stays what was asked — the two are always separate fields, never merged or hidden. |
| Malformed query parameters (e.g. `amount=abc`, an unparsable `date`, `from`/`to` missing entirely) | 400 `invalid_request` | Rejected with the same `{error, message}` shape as every other rejection, instead of FastAPI's default validation error format. |
| Future date | 400 `date_in_future` | Rejected before any upstream call. |
| Date before `1999-01-04` (series start) | 400 `date_before_series_start` | Rejected before any upstream call. |
| Unknown or invalid currency code (`from` and/or `to`) | 400 `unknown_currency` | Rejected before any upstream call. |
| `from` equals `to` | 400 `same_currency` | Rejected before any upstream call. |
| Invalid `amount` (missing, zero, negative, or more than 4 decimal places) | 400 `amount_*` | Rejected before any upstream call, with the matching error code. |
| Upstream is slow | 504 `upstream_timeout` | No rate is ever invented, and nothing is ever reported as 200. |
| Upstream errors or is unreachable | 502 `upstream_error` | Same principle: no invented rate, no false 200. |
| Upstream returns a broken/invalid body | 502 `upstream_invalid_response` | Same principle: no invented rate, no false 200. |
| Repeat request for the same `(from, to, resolved date)` | 200 | Served from an in-process cache — no second upstream call. |