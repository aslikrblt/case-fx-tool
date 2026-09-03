# Notes

## Decisions

When the ECB has published no rate for the asked date (weekend, holiday), the
service takes the upstream's own fallback rate as-is instead of reimplementing
weekend/holiday logic itself — the ECB calendar isn't something to hardcode,
and the upstream already tells us which date its rate actually belongs to.
`rate_date` is always read from the upstream's own `"date"` field, never
assumed or copied from what was asked; `asked_date` is kept as a separate
field populated only from the request. The two are never merged, so a
customer (or the agent talking to them) can always see when a rate is from a
different day than the one requested. Validation runs before any upstream
call, so an obviously bad request (bad amount, unknown currency, `from ==
to`, an out-of-range date) never spends a network round trip — or a cache
slot — on something already known to be wrong. The cache key includes the
resolved date, not just the currency pair, because keying by pair alone (as
`tool.py` does) means the first rate fetched for a pair silently answers
every later question about it regardless of the date being asked — exactly
the bug the Part B review found.

## With another day

- `SUPPORTED_CURRENCIES` in `app/validation.py` is a hardcoded list of the 30
  currencies Frankfurter publishes today; nothing keeps it in sync if that
  list ever changes. I'd query `GET /v1/currencies` once at startup (or cache
  it with its own short TTL) instead of hardcoding it.
- `get_http_client()` in `app/upstream.py` opens and tears down a brand-new
  `httpx.AsyncClient` on every single request instead of reusing one client
  (with connection pooling) for the app's lifetime. Fine at this scale, but
  wasteful under real load — I'd wire it through FastAPI's lifespan instead.
- The rate cache (`app/cache.py`) has no TTL or eviction. That's harmless for
  a specific historical date (that rate never changes), but a "latest"
  lookup is cached forever for the life of the process — a `/tools/convert`
  call made this morning stays cached even after the ECB publishes a new
  rate later the same day. I'd add a short TTL, or invalidate latest-only
  entries once a new business day starts.

## AI tools

Claude Code, for essentially the whole build — wiring up `run.sh`/config,
the upstream client with an injectable HTTP client, network-free test
infrastructure (pytest + `httpx.MockTransport` + a FastAPI dependency
override), the conversion logic itself, weekend/holiday handling, input
validation, upstream-failure handling, caching, and the README — one
focused commit at a time. Each step was scoped narrowly on purpose, and I
checked actual behavior (running the tests, and a couple of times booting a
real fake upstream server end to end) before moving to the next.

## One thing the AI got wrong

`/tools/convert` declares `amount`, `date`, `from`, and `to` as typed FastAPI
`Query` parameters, so FastAPI/Pydantic parses and validates them before the
request ever reaches `app/validation.py`. A non-numeric `amount`, a malformed
`date`, or a missing `from`/`to` never reaches my own validation code at
all — it falls straight into FastAPI's own automatic 422 response, shaped
like `{"detail": [...]}`, not the `{"error", "message"}` schema every other
rejection in this service uses and that the README promises for *every*
non-2xx response. Claude Code had built solid validation for every case
explicitly listed in the brief (bad amount, unknown currency, same currency,
out-of-range date) but never checked what happens when FastAPI's own type
coercion runs before that validation gets a chance to. I noticed it by
testing the service against its own stated contract rather than against the
brief's scenario list: `?amount=abc&from=EUR&to=TRY` doesn't come back in
the documented shape. I added a global handler for `RequestValidationError`
that maps it onto the same `{"error": "invalid_request", "message": "..."}`
shape, added the new code to `validation.py`'s `ErrorCode` registry and to
the README's error table, and added tests covering a non-numeric amount, an
invalid date string, and a missing `from` parameter (commit: "fix: return
consistent error schema for malformed query params").