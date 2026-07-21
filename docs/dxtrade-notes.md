# DXtrade / Futures Elite integration notes (Phase 2 discovery spike)

> Purpose: record what we know about the DXtrade execution API so the live
> adapter and worker can be built and, more importantly, so the **fixture shapes
> the whole test suite depends on are pinned down**. Everything in CI runs off
> `tests/fixtures/dxtrade/*.json` and `tests/fixtures/statements/*.csv` — **no
> live prop connection is ever used in tests.**

## Terminology (the load-bearing fact)

- **dxFeed** = market data only (quotes, tick specs). It does **not** carry the
  user's orders/positions/fills. The user's phrase "dxFeed prop" is a misnomer.
- **DXtrade** (Devexperts) = the execution/trading platform Futures Elite runs.
  Its REST + Push (WebSocket) API is the **authoritative source of the user's
  fills**. This is what Phase 2 integrates for fills.

## Auth model (session login, not an API key)

The user has only a **platform login** — username + password + a broker/domain
code — the same credentials the DXtrade web client uses. There is no developer
API token. The adapter therefore authenticates the way the web client does:

1. `POST {BASE_URL}/login` (session-auth) with `{username, password, domain}` →
   returns a session token / cookie.
2. Reuse that session for REST snapshot calls and to open the Push WebSocket.

Config (env, read by the worker — see `config.py` / `.env.example`):
`DXTRADE_USERNAME`, `DXTRADE_PASSWORD`, `DXTRADE_DOMAIN`, `DXTRADE_BASE_URL`,
`DXTRADE_WS_URL`.

## Fill/execution event shape (normalized → `Fill`)

Each execution the adapter emits is normalized to `sources/base.py:Fill`:

| Fill field          | DXtrade concept                    |
|---------------------|------------------------------------|
| `external_exec_id`  | execution id (idempotency key)     |
| `external_order_id` | parent order id                    |
| `account`           | account id                         |
| `symbol`            | instrument root (uppercased)       |
| `action`            | `buy` / `sell`                     |
| `quantity`          | filled contracts (> 0)             |
| `price`             | fill price (Decimal)               |
| `fee`               | commission for this fill           |
| `executed_at`       | execution time (→ naive UTC)       |

The recorded/anonymized samples live in `tests/fixtures/dxtrade/`:
`simple_round_trip`, `partial_fills`, `scale_in_out`, `multiple_round_trips`,
`position_flip`, `unknown_symbol`, `duplicate_replay`. These are stored in the
**normalized** `Fill` dict shape (what `StubTradeSource.from_dicts` /
`fill_from_dict` consume) so they drive the pipeline directly; the live
`DXtradeSource` is responsible for mapping raw DXtrade JSON into this shape and
is unit-tested against its own raw samples.

## REST snapshot + cursor (backfill / replay)

`fetch_fills(since=last_cursor)` pulls the executions since a cursor (server
sequence / last exec id) for startup backfill and reconnect replay. Correctness
does **not** rest on the cursor: the `broker_fills` upsert (unique
`external_exec_id`) + deterministic per-round-trip `external_id` guarantee that a
re-fetched/overlapping fill produces zero new trades. The cursor only narrows the
replay window.

## ToS / legality — RISK GATE

Whether Futures Elite's specific DXtrade deployment permits programmatic/session
login outside the browser is **uncertain and may violate the prop firm's terms.**
This is unresolved and cannot be confirmed from here.

**Decision:** treat the **CSV/statement import path as the primary, compliant
path** (`sources/csv_statement.py`, `POST /api/sync/import`). It shares the exact
same reconciliation pipeline, so the feature delivers full value even if live
streaming is disallowed. `DXtradeSource` + the streaming worker are built behind
the same interface and are **fully fixture-covered**, but shipping/enabling them
live is gated on the user confirming their firm allows it. Never ship a live
connection that hammers the broker; back off aggressively on auth failure.

## Credentials handling

Passwords live in `.env` or a **gitignored** local secret file written by
`POST /api/sync/credentials`. They are **never** returned by any API, never
logged, and never committed. This is adequate for a single-user tutorial app but
is not a hardened secret manager (flagged as a known limitation).
