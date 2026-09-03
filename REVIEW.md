# Review of tool.py

Each finding is the running service's answer beside what the upstream said to the
same question at the same moment. `tool.py` is untouched; the one case needing a
stand-in repointed `tool.UPSTREAM` from a local session. Ranked by what reaches a
customer: how often it fires, how invisible it is, how far wrong.

## 1. The cache answers a question it was never asked

`key = f"{base}-{target}"` leaves out the date and nothing expires, so the first
rate fetched for a pair answers every later question about it, wearing whatever
date the new caller asked for.

```
?from_=EUR&to=USD&on=2020-03-16 -> rate 1.12, rate_date 2020-03-16
?from_=EUR&to=USD               -> rate 1.12, rate_date 2026-09-02
upstream /v1/latest EUR->USD    -> date 2026-09-01, 1.159
```

**To a customer:** one person asks about March 2020 and everyone after them is
quoted that rate as today's, until the process restarts. A 10,000 EUR invoice
comes back as 11,200 USD instead of 11,590; on EUR/TRY the same poisoning is a
factor of eight. Plausible, well formed, untrue.

## 2. The date on the answer is manufactured from the question

Both return paths report `str(on or date.today())`. The upstream's own `date`
field is never read, though the docstring promises `"""Return (rate, the date the
rate belongs to)"""`.

```
on=2026-08-30 -> 0.86, dated 2026-08-30 | upstream: 0.8572 on 2026-08-28
on=2026-09-10 -> 0.94, dated 2026-09-10 | upstream: date 2026-09-01
on=2030-01-01 -> 7.47, dated 2030-01-01 | upstream: 404 not found
```

**To a customer:** Friday's rate presented as Sunday's, and that is the field an
invoice is checked against later. Then a rate for a day that has not happened,
because the upstream answers near-future dates with 200 and nothing fails loudly.
Then a rate for 2030 the upstream refused to give: invented out of nothing.

The comment above the fallback (lines 36-40) explains it as "the ECB publishes
nothing on weekends". The ECB does not, but the *upstream* does, answering
Saturday and Sunday with 200 and Friday's date — confirmed directly: `on=2026-08-29`
(a Saturday) returns 200 with `"date": "2026-08-28"` from Frankfurter itself,
`rates` already populated, so `if target not in payload.get("rates", {})` never
trips on a weekend. It fires instead on a body with no `rates` key at all: an
unknown currency, or a date outside the series. There, it re-asks `/latest`, gets
a real, current rate, and — because of the same date-fabrication bug — labels
that live rate with whatever date was originally asked for, including a date the
upstream just refused to answer. That comment is why this finding looks
reasonable at first glance: the author's model of the upstream was wrong, and
everything downstream inherited it.

## 3. The documented call is not the call the code implements

The handler declares `from_` and `on`, so the brief's `from` and `date` are never
read and take their defaults, `EUR` and "latest". `asked_date` is absent entirely.

```
?amount=250&from=USD&to=TRY&date=2026-08-28 -> from EUR, 55.91, result 13977.5
upstream USD->TRY on 2026-08-28: 48.245     -> the answer should be 12061.25
```

**To a customer:** 250 dollars quoted as 250 **euros** at another day's rate,
silently — no error, no 4xx, just the wrong currency pair and the wrong date,
both defaulted without a word, on every single call that uses the interface
exactly as documented.

## The one I would fix before shipping tonight

Finding 3, the parameter mismatch. The other two findings are severe but
conditional: cache poisoning needs a second, differently-dated request for the
same pair; date fabrication needs a weekend, a future date, or a date outside
the series. The parameter mismatch needs nothing — it fires on the first call
anyone makes using the interface exactly as the README describes it, with no
error and no way to notice short of comparing the response to what was asked.
Right now the service does not correctly perform its one documented job for a
single ordinary request. It's also the cheapest fix of the three: correcting two
parameter bindings, not touching any conversion or caching logic.

## Things that look suspicious but are fine

- **No timeout on the client.** httpx defaults to five seconds on every phase.
  Confirmed two ways: `print(httpx.AsyncClient().timeout)` returns
  `Timeout(timeout=5.0)`, and by pointing a stand-in upstream at a 6-second
  artificial delay — the request failed with a timeout at the 5-second mark
  instead of hanging indefinitely.
- **`except Exception` swallowing a cancelled request.** It does not.
  `asyncio.CancelledError` has been a `BaseException`, not an `Exception`, since
  Python 3.8.
- **The unbounded cache.** The write happens only after a lookup succeeds, so
  nothing a caller invents lands in it. Its problem is its key (finding 1), not
  its size.
- **Rounding the result to two decimals.** Correct. Money is quoted in cents.
- **Rate-fetching and conversion logic living in one file.** Worth splitting in a
  larger service, but at this size it costs the customer nothing — a style
  preference, not a defect.