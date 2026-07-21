# Feature: Trading Journal — Phase 2 (Automated DXtrade Fill Sync)

> Spec ID: `trading-journal-phase2-dxtrade-automated`
> Scope: **Phase 2 only** — automatically populate the journal with the trades the user actually executed at their prop firm **Futures Elite** (which runs on the **Devexperts DXtrade** platform), in **real time**, while keeping Phase 1's manual entry fully working. Introduces a pluggable trade-source adapter layer, a fill→closed-trade reconciliation pipeline, an `instruments` tick-spec table, source/dedupe columns on `trades`, a background streaming worker, and connection/import UI.
> Builds directly on: `specs/trading-journal-phase1-manual-futures.md`. Reuses Phase 1's `trades` table, its `compute_pnl` single-source-of-truth convention (`ticks` = per-contract signed ticks; the contract multiplier applies to dollars only), and its model/schema/controller/view/island structure.

## Terminology clarification (read first)

The user refers to their prop feed as **"dxFeed prop."** This name conflates two distinct Devexperts products, and the distinction is the load-bearing technical fact of this whole phase:

- **dxFeed** is a **market-data** service only — quotes, order book, time & sales, and instrument/tick specifications. It does **NOT** carry the user's own orders, positions, or fills. It cannot tell us what the user traded.
- **DXtrade** (Devexperts DXtrade) is the **execution/trading platform** Futures Elite actually runs. It holds every order, position, and fill for the account. Its **REST + Push (WebSocket) API** — the same API the DXtrade web front-end itself calls — is the **authoritative source of the user's fills**.

Therefore: **the execution/fills source for Phase 2 is DXtrade, not dxFeed.** dxFeed may still be used as an auxiliary source for **live prices and instrument tick specifications** (populating/verifying the `instruments` table), but never for the user's fills. This spec says "DXtrade" everywhere the user said "dxFeed prop."

## Feature Description

Phase 1 gave the user a manual futures journal: they type each completed trade and the app computes tick-based P&L and summary stats. Phase 2 removes the typing for their real trading account: the journal **auto-logs a closed trade the moment a position flattens** at Futures Elite (DXtrade), and keeps the manual form as a first-class, coexisting path (hybrid).

Concretely, Phase 2 adds:

1. **A pluggable `TradeSource` adapter interface** with two real adapters — a **DXtrade session-auth REST + Push (WebSocket) streaming adapter** (primary, real-time) and a **CSV/statement import adapter** (fallback / backfill) — plus a **stub adapter** for tests. All adapters emit a normalized `Fill` and feed **one shared reconciliation pipeline**.
2. **A reconciliation pipeline** that aggregates per-order fills into closed `trades` rows: it assembles entry + exit legs into one round-trip, handling **partial fills, scale-ins/scale-outs (weighted-average entry/exit), and multiple round-trips per symbol/session**, then reuses Phase 1's `compute_pnl` to write `ticks`/`gross_pnl`/`net_pnl`. Tick specs come from a new **`instruments`** table (the Phase-1-anticipated `symbol → tick_size, tick_value, multiplier` map), snapshotted onto each trade for historical accuracy.
3. **Hybrid coexistence + dedupe**: a `source` column (`manual` | `dxtrade`) and a unique `external_id` on `trades`, plus a raw-fill store so **re-processing and reconnects never double-count**. Imports that look like a pre-existing manual trade are **flagged**, not silently merged.
4. **A background streaming worker** (a separate process launched via the existing `Procfile`) that holds the persistent DXtrade WebSocket, with reconnect/backoff and a durable cursor so restarts resume without duplicating.
5. **Connection & import UI** inside the existing `journal` island: a connection/status panel (credentials entry, connect/disconnect, a live "connected / streaming" indicator), **source badges** on trade rows, dedupe visibility ("N imported, M skipped as duplicates"), a manual **Import CSV** action, and a manual **Reconcile/backfill** action. The trades table and stats header update live as trades stream in.

Everything is testable in CI with **no live prop connection**: adapters are mocked, DXtrade traffic is served from **recorded fixtures / a fake source**, and the fill-aggregation and dedupe logic are covered thoroughly. A Playwright E2E drives the automated flow against a stub source.

## User Story

As a **futures trader with a funded account at Futures Elite (a DXtrade prop firm)**
I want to **connect my prop platform login once and have every closed trade automatically appear in my journal in real time, with correct tick-based P&L and no duplicates**
So that **my journal reflects what I actually traded without manual re-entry, while I can still add or correct trades by hand and clearly see which trades came from the broker versus me.**

## Problem Statement

Phase 1 requires the user to hand-type every trade — error-prone, slow, and easy to forget, and the typed tick specs can be inconsistent from trade to trade. The user's real fills already live in one authoritative place: their Futures Elite account on the DXtrade platform. But:

- **The obvious feed name is a red herring.** "dxFeed" is market data and does not contain the user's fills; the fills live in the **DXtrade** trading API. Any design that reaches for dxFeed for fills is wrong.
- **The user has only a platform login** (DXtrade username + password + likely a broker/domain code) — **no separate API key or token**. The design must authenticate the same way the DXtrade web client does (a session login) rather than assuming a developer API key.
- **Real fills are per-order executions, not trades.** A single "trade" the user thinks of (e.g. "I scalped 2 ES for +8 ticks") can be several fills — partial fills, scale-ins, scale-outs — and a session can contain many round-trips per symbol. Something must **aggregate fills into the closed round-trip trades** the journal stores, and compute correct P&L per Phase 1's tick convention.
- **Real-time + restarts + reconnects invite duplicates.** A streaming feed that reconnects, replays, or is restarted must never log the same trade twice, and must never double-count against a trade the user already entered manually.
- **Whether Futures Elite's specific DXtrade deployment permits programmatic/session login outside the browser (and the ToS around it) is uncertain.** The design cannot bet everything on the streaming path; it needs a graceful fallback and an explicit discovery step.

## Solution Statement

Build an **adapter + pipeline** on top of Phase 1, keeping Phase 1's data model and `compute_pnl` untouched as the P&L source of truth.

- **`TradeSource` adapter interface (pluggable).** A plain base class (`src/app/sources/base.py`) defining a normalized `Fill` dataclass and two capabilities: `stream_fills()` (async generator, for live sources) and `fetch_fills(since)` (batch, for statement/backfill sources). Concrete adapters:
  - **`DXtradeSource`** — authenticates with the user's platform credentials against DXtrade's **session-auth REST** endpoint (the flow the web client uses), then subscribes to the **Push (WebSocket) API** for order/position/fill events, normalizing each execution into a `Fill`. Also supports a REST `fetch_fills(since)` snapshot for backfill and reconnect replay.
  - **`CsvStatementSource`** — parses a DXtrade/Futures Elite fills or statement CSV export into `Fill`s (fallback when streaming/session-login is unavailable or disallowed).
  - **`StubTradeSource`** — replays recorded fixtures for tests/dev/E2E (no network).
- **One shared reconciliation pipeline** (`src/app/controllers/reconciliation.py`): normalized `Fill`s → raw-fill persistence (idempotent by execution id) → per-account/symbol **round-trip aggregation** (weighted-average entry/exit, partial-fill and scale-in/out aware, position-flip aware) → closed `trades` rows written via the existing controller and `compute_pnl`, with tick specs looked up from `instruments` and **snapshotted** onto the row. Deterministic `external_id` per round-trip provides idempotent dedupe.
- **Schema additions** (one new Alembic revision chained onto the current head `a1b2c3d4e5f6`): `trades.source`, `trades.external_id` (unique, nullable), plus new tables `instruments`, `broker_fills` (raw idempotency/cursor store), and `sync_state` (single-row connection/cursor/status). Manual trades keep `source='manual'`, `external_id=NULL` (multiple NULLs are allowed under a unique index on both PostgreSQL and the SQLite test DB), so **Phase 1 behavior is preserved exactly**.
- **Background streaming worker** (`src/app/worker/dxtrade_worker.py`, launched via a new `worker:` line in `Procfile` and a `script/worker` dev launcher): a single, separate asyncio process that owns the persistent WebSocket, ingests fills through the same controller code under an app context, reconnects with exponential backoff, and persists a durable cursor. It never runs inside a request; the web app and worker communicate only through the database. The web UI polls a status endpoint and refetches trades when new ones land.
- **API + UI**: a `sync_bp` blueprint (`/api/sync/*`) for status, connect/disconnect, credentials, CSV import, and manual reconcile; the `journal` island gains a **ConnectionPanel**, **source badges**, dedupe result display, and status polling so streamed trades appear live.
- **Testable without the prop**: adapters are injected; DXtrade traffic is replaced by fixtures / a fake source; a dev/test-only ingest endpoint lets the Playwright E2E push a fixture fill batch through the real pipeline and assert the source badge, dedupe, and live stats update — with no network.

### Key design decisions (recommended, with justification)

**1. Fills → closed trades via weighted-average round-trip aggregation → RECOMMENDATION: aggregate to flat, exact for fully-closed round-trips.**
A round-trip opens when net position leaves flat and closes when it returns to exactly 0. Entry legs (position-increasing fills) contribute a **contracts-weighted average entry price**; exit legs (position-reducing fills) a **weighted average exit price**. Because a closed round-trip has equal total entry and exit quantity `Q`, the weighted-average method yields the **exact** realized P&L in price points (`Σ(exit_i·qty_i) − Σ(entry_j·qty_j)`), so feeding `avg_entry`, `avg_exit`, and `contracts=Q` into Phase 1's `compute_pnl` reproduces true realized dollars. Partial fills and scale-in/out are handled naturally; a position **flip** (a fill that crosses 0) is split at the zero-crossing into a closing leg for the old round-trip and an opening leg for the new one. `fees` = sum of all constituent fills' fees. `entry_at` = first entry fill time; `exit_at` = last exit fill time.
- *Why not lot-matching (FIFO/LIFO)?* For a fully-closed round-trip both give identical net dollars; weighted-average is simpler, matches how the journal already models one trade as one avg-entry/avg-exit row, and needs no per-lot storage. (FIFO is future work if the user ever wants per-lot tax reporting.)
- *Open (still-running) positions are not logged as trades* — consistent with Phase 1 "closed trades only." A partially-closed position stays pending until it flattens.

**2. Idempotency/dedupe via a raw-fill store + deterministic `external_id` → RECOMMENDATION: persist every fill keyed by its broker execution id; derive a stable `external_id` per round-trip.**
`broker_fills` stores each execution once (unique `external_exec_id`); ingestion is an upsert, so a reconnect/replay/restart that re-delivers a fill is a no-op. Reconciliation is a **pure function of the stored fills**, so re-running it is deterministic. Each emitted trade's `external_id` is derived from the round-trip's constituent execution ids (a stable hash), so re-reconciliation finds the existing row and **updates-or-skips instead of inserting** — never double-counting.
- *Why store raw fills at all?* It is the cursor/audit/idempotency backbone: restarts resume from the last stored fill, reconciliation can be re-run after a bug fix, and support questions ("why did this trade appear?") are answerable.

**3. `instruments` tick-spec table (Phase-1-anticipated) with per-trade snapshot → RECOMMENDATION: introduce it now; keep `trades` snapshot columns.**
Imported fills carry no tick spec, so `symbol → tick_size, tick_value, multiplier` is looked up from `instruments` (seeded with common CME futures; verifiable/extendable via dxFeed). The looked-up spec is **copied onto the trade row** (`trades` already stores per-trade `tick_size`/`tick_value` from Phase 1), so later edits to an instrument never rewrite historical P&L — exactly the snapshot rationale Phase 1 established. A symbol with **no known spec** does not guess: its trade is created in a `needs_review` state (see decision 6) and surfaced in the UI.

**4. Real-time streaming runs in a separate worker process, not in a request or a Flask thread → RECOMMENDATION: a `Procfile` `worker:` process.**
Flask serves one request at a time per worker and gunicorn runs multiple workers; a WebSocket that must live for hours cannot live inside a request, and starting it inside every gunicorn worker would open N duplicate broker sessions. A **single dedicated process** (`src/app/worker/dxtrade_worker.py`) owns the socket, shares the DB and controller code under an app context, and communicates with the web tier **only through the database** (fills + `sync_state`). This is the simplest correct topology for this repo (it already ships a `Procfile`), avoids intra-process threading fragility, and lets the UI reflect state by polling. Connect/disconnect is a **desired-state flag** in `sync_state` the worker observes — the web request never touches the socket.

**5. Credentials live in `.env`; the UI can write them to a gitignored runtime secret store → RECOMMENDATION: env as source of truth, optional write-through, never in VCS or logs.**
DXtrade credentials (`DXTRADE_USERNAME`, `DXTRADE_PASSWORD`, `DXTRADE_DOMAIN`, `DXTRADE_BASE_URL`, `DXTRADE_WS_URL`) are read from the environment by the worker. The UI credentials form (per the requirement to enter credentials) posts to `/api/sync/credentials`, which writes to a **gitignored** local secrets file the worker also reads — so a single-user tutorial deployment can configure without shell access. Passwords are **never** returned by the API, never logged, and the status endpoint only reports *whether* credentials are configured. This tradeoff (plaintext local secret vs. a real secret manager) is called out in Notes as a known risk.

**6. Imported-vs-manual duplicates are flagged, never auto-merged → RECOMMENDATION: hard dedupe only on `external_id`; heuristic manual overlaps are surfaced for the user.**
Two imports of the same round-trip share an `external_id` → hard dedupe. But a manual trade has `external_id=NULL`, so an import that overlaps a manually-entered trade cannot be deduped by id. Auto-deleting either side risks destroying real data. Instead the pipeline **detects likely overlaps** (same symbol/side/contracts with entry & exit prices equal and times within a small tolerance) and marks the imported trade `needs_review` with a `duplicate_of` pointer, shown in the UI for the user to keep or discard. This satisfies "imports dedupe and never double-count" for imports while never silently mutating the user's manual data.

**7. DXtrade session-auth uncertainty → RECOMMENDATION: a discovery/spike task first, and a CSV fallback that shares the pipeline.**
Because Futures Elite's specific DXtrade deployment may or may not permit programmatic session login (and the ToS is uncertain), the first implementation task is a **discovery spike** to confirm the auth flow, endpoints, and event shapes and to **capture recorded fixtures**. The `CsvStatementSource` fallback (statement export → same reconciliation pipeline) means the feature delivers value even if live streaming is unavailable or disallowed. Both paths converge on one pipeline and one set of tests.

## Relevant Files

Use these files to implement the feature:

**Backend — reference (Phase 1 patterns to follow, do not rewrite the P&L math)**
- `src/app/controllers/trade.py` — **reuse `compute_pnl` verbatim** as the P&L source of truth; the reconciliation pipeline calls it. `_to_naive_utc`, `_apply_inputs`, `create_trade` are the write path to mirror.
- `src/app/models/trade.py` — the `Trade` model to extend with `source`/`external_id`; keep all Phase 1 columns and the snapshot rationale.
- `src/app/schemas/trade.py` — Pydantic v2 style (field/model validators, terse messages, `float` response fields) to mirror for the new sync schemas; add `source`/`external_id` to `TradeResponse`.
- `src/app/views/journal.py` — thin-route + `_validation_error`/`_not_found` helpers to reuse in the new `sync_bp`.
- `src/app/errors.py` — content-negotiated JSON/HTML handlers; new API errors stay consistent with these.
- `src/app/config.py` — add DXtrade/worker config (URLs, poll interval, backoff caps) as `Config` attributes read from env; testing config stays SQLite in-memory.
- `src/app/__init__.py` — app factory / blueprint registration pattern; register `sync_bp`.
- `tests/conftest.py` — `app`/`client` fixtures (SQLite in-memory, `create_all`/`drop_all` per test); extend with fixtures for instruments seed, fixture fills, and a stub source.

**Backend — modify**
- `src/app/models/trade.py` — add `source` (String(16), NOT NULL, default `'manual'`), `external_id` (String(128), nullable, unique), and `review_status` (String(16), default `'ok'`) + `duplicate_of` (Integer, nullable) for the flagging in decision 6.
- `src/app/models/__init__.py` — export new models (`Instrument`, `BrokerFill`, `SyncState`).
- `src/app/schemas/trade.py` — add `source`, `external_id`, `review_status` to `TradeResponse`.
- `src/app/controllers/__init__.py` — export new controller functions.
- `src/app/schemas/__init__.py` — export new sync/instrument schemas.
- `src/app/views/__init__.py` — register `sync_bp` alongside `journal_bp`.
- `src/app/config.py` — DXtrade + worker settings.
- `script/db-seed` — seed the `instruments` table with common CME futures (ES, MES, NQ, MNQ, CL, MCL, GC, MGC, RTY, YM, 6E, etc.); keep the Phase 1 sample-trade seeding.
- `Procfile` — add a `worker: python -m app.worker.dxtrade_worker` line.
- `requirements.txt` — add `websockets` and `httpx` (justified below).
- `.env.example` — add the `DXTRADE_*` and worker settings (with placeholder values).
- `.gitignore` — ignore the runtime secrets file written by the credentials endpoint (e.g. `.secrets/dxtrade.json`).

**Frontend — modify**
- `frontend/src/journal/types.ts` — add `source: 'manual' | 'dxtrade'`, `external_id: string | null`, `review_status: string` to `Trade`; add `SyncStatus`, `ImportResult` types.
- `frontend/src/islands/journal/JournalIsland.tsx` — own sync status state, poll `/api/sync/status`, refetch trades+stats when new trades land, render `ConnectionPanel`.
- `frontend/src/islands/journal/TradeTable.tsx` — add a **Source** column rendering a `SourceBadge`; show a "needs review / possible duplicate" indicator.
- `frontend/src/main.ts` — no change (island already registered); new components are internal to the journal island.

**Frontend — reference**
- `frontend/src/journal/api.ts` — `request` wrapper + `ApiRequestError` to reuse for the sync API (including multipart for CSV upload).
- `frontend/src/islands/journal/StatsHeader.tsx`, `TradeForm.tsx` — component/Tailwind conventions to match.
- `frontend/src/journal/format.ts` — `formatMoney`/`formatTicks`/`pnlColor` reuse.

### New Files

**Backend — sources (adapter layer)**
- `src/app/sources/__init__.py` — exports `TradeSource`, `Fill`, and the concrete adapters.
- `src/app/sources/base.py` — `Fill` dataclass (normalized execution) + `TradeSource` base class (plain class; `stream_fills()` async generator and `fetch_fills(since)` raising `NotImplementedError` by default) + `TradeSourceError`.
- `src/app/sources/dxtrade.py` — `DXtradeSource`: session-auth REST login (`httpx`), Push WebSocket subscription (`websockets`), event → `Fill` normalization, `fetch_fills(since)` REST snapshot for backfill/replay.
- `src/app/sources/csv_statement.py` — `CsvStatementSource`: parse a DXtrade/Futures Elite fills CSV (stdlib `csv`) → `Fill`s; tolerant column mapping.
- `src/app/sources/stub.py` — `StubTradeSource`: replays a list/fixture of `Fill`s via `stream_fills()`/`fetch_fills()`; no network. Used by tests, dev, and the E2E ingest endpoint.

**Backend — models / controllers / schemas / views**
- `src/app/models/instrument.py` — `Instrument` (`symbol` unique, `description`, `tick_size` Numeric(18,8), `tick_value` Numeric(18,4), `multiplier` Numeric(18,4) nullable, `exchange` String, timestamps).
- `src/app/models/broker_fill.py` — `BrokerFill` (raw idempotency/cursor store: `external_exec_id` unique, `external_order_id`, `account`, `symbol`, `action` buy/sell, `quantity`, `price` Numeric(18,6), `fee` Numeric(18,4), `executed_at`, `source`, `raw` Text/JSON, `ingested_at`, `processed` bool, `trade_id` FK→trades nullable).
- `src/app/models/sync_state.py` — `SyncState` (single row: `enabled` bool, `status` String, `last_cursor` String, `last_fill_at` DateTime, `last_synced_at` DateTime, `last_error` Text, `updated_at`).
- `src/app/controllers/instrument.py` — `get_spec(symbol)`, `upsert_instrument(...)`, `list_instruments()`, `seed_default_instruments()`.
- `src/app/controllers/reconciliation.py` — the pipeline: `aggregate_round_trips(fills) -> list[RoundTrip]` (pure), `ingest_fills(fills, source) -> ReconcileResult` (persist raw fills idempotently, aggregate, create/dedupe trades, flag manual overlaps), plus `reconcile_all()` (re-run over stored fills). Reuses `compute_pnl` and `create_trade`.
- `src/app/controllers/sync.py` — `get_sync_state()`, `set_enabled(bool)`, `record_status(status, error=None, cursor=None)`, `credentials_configured()`, `save_credentials(...)`, `load_credentials()`, `import_csv(file_stream) -> ReconcileResult`.
- `src/app/schemas/sync.py` — `SyncStatusResponse`, `CredentialsPayload` (write-only), `ReconcileResultResponse` (created/updated/skipped/flagged counts), `InstrumentResponse`.
- `src/app/views/sync.py` — `sync_bp`: `GET /api/sync/status`, `POST /api/sync/connect`, `POST /api/sync/disconnect`, `POST /api/sync/credentials`, `POST /api/sync/import` (multipart CSV), `POST /api/sync/reconcile`, `GET /api/instruments`, and a **dev/test-only** `POST /api/sync/_test/ingest` (guarded by `app.testing`/`DEBUG`).

**Backend — worker**
- `src/app/worker/__init__.py`
- `src/app/worker/dxtrade_worker.py` — asyncio entrypoint (`python -m app.worker.dxtrade_worker`): creates an app context, loops honoring `sync_state.enabled`, connects `DXtradeSource`, streams fills → `ingest_fills`, updates status/cursor, reconnects with exponential backoff, and on startup replays via `fetch_fills(since=last_cursor)` before streaming.

**Backend — tests + fixtures**
- `tests/test_reconciliation.py` — aggregation + dedupe unit tests (all edge cases below).
- `tests/test_instrument.py` — spec lookup, seeding, unknown symbol.
- `tests/test_csv_import.py` — `CsvStatementSource` parsing + end-to-end import via the pipeline.
- `tests/test_dxtrade_source.py` — `DXtradeSource` event→`Fill` normalization + `stream_fills` against a fake in-process socket / recorded fixtures (no network).
- `tests/test_sync_view.py` — `/api/sync/*` endpoints (status, connect/disconnect toggles `enabled`, credentials write-only, import, reconcile, test-ingest), including source badge/dedupe visible in `TradeResponse`.
- `tests/test_worker.py` — worker loop unit test with a `StubTradeSource` and a fake backoff/clock (no real sleeping/network): ingests fixtures, updates cursor, resumes without duplicating.
- `tests/fixtures/dxtrade/` — recorded fill sequences (JSON): `simple_round_trip.json`, `partial_fills.json`, `scale_in_out.json`, `multiple_round_trips.json`, `position_flip.json`, `unknown_symbol.json`, `duplicate_replay.json`.
- `tests/fixtures/statements/` — sample CSV exports: `futures_elite_fills.csv`, `malformed.csv`.

**Frontend — new**
- `frontend/src/journal/sync.ts` — types + typed fetch wrappers: `getSyncStatus`, `connect`, `disconnect`, `saveCredentials`, `importCsv` (multipart), `reconcile`, and (dev/test) `testIngest`.
- `frontend/src/islands/journal/ConnectionPanel.tsx` — connection status badge (disconnected / connecting / streaming / error), Connect/Disconnect, credentials form, Import CSV, Reconcile, and dedupe result display ("N imported, M skipped, K flagged").
- `frontend/src/islands/journal/SourceBadge.tsx` — small badge for `manual` vs `dxtrade` (+ a "review" variant).

**Frontend — tests**
- `frontend/tests/journal/sync.test.ts` — Vitest for `sync.ts` wrappers (status parsing, multipart body, error surfacing).
- `frontend/tests/journal/connectionPanel.test.ts` — Vitest for panel state logic (badge label per status, dedupe summary formatting).

**E2E**
- `e2e/journal-sync.spec.ts` — Playwright: drive the automated flow via the stub source (test-ingest endpoint) — assert a `dxtrade` source badge appears, ingesting the same batch twice keeps one row (dedupe), and the stats header updates. Keep `e2e/journal.spec.ts` (Phase 1 manual) passing.

## Data Model / Migration Plan

One new Alembic revision, `add_source_and_broker_sync`, with `down_revision = 'a1b2c3d4e5f6'` (the current head — `create_trades_table`). `upgrade()` alters `trades` and creates three tables; `downgrade()` reverses in dependency order.

### `trades` — added columns (Phase 1 columns unchanged)

| Column          | Type          | Null | Default    | Notes |
|-----------------|---------------|------|------------|-------|
| `source`        | String(16)    | no   | `'manual'` | `manual` \| `dxtrade`. Backfill existing rows to `'manual'`. |
| `external_id`   | String(128)   | yes  | NULL       | broker round-trip id; **unique** (nullable → many manual NULLs allowed on PG + SQLite). |
| `review_status` | String(16)    | no   | `'ok'`     | `ok` \| `needs_review` (unknown tick spec or possible manual duplicate). |
| `duplicate_of`  | Integer       | yes  | NULL       | FK→`trades.id`; set when flagged as a likely manual duplicate. |

- Add a **unique index** on `external_id` (`uq_trades_external_id`). PostgreSQL and SQLite both permit multiple NULLs under a unique index, so manual rows are unaffected.
- Migration must **backfill** `source='manual'`, `review_status='ok'` for any existing rows before setting NOT NULL (use `server_default` then column update, matching the batch/`server_default` idiom; SQLite needs `batch_alter_table` for altering columns — use `op.batch_alter_table('trades')`).

### New table: `instruments`

| Column        | Type            | Null | Notes |
|---------------|-----------------|------|-------|
| `id`          | Integer PK      | no   | |
| `symbol`      | String(16)      | no   | **unique**, uppercased root symbol (`ES`, `MNQ`, …) |
| `description` | String(120)     | yes  | e.g. "E-mini S&P 500" |
| `tick_size`   | Numeric(18,8)   | no   | > 0 |
| `tick_value`  | Numeric(18,4)   | no   | USD per tick per contract, > 0 |
| `multiplier`  | Numeric(18,4)   | yes  | contract multiplier (informational) |
| `exchange`    | String(16)      | yes  | e.g. `CME` |
| `created_at`  | DateTime        | no   | UTC |
| `updated_at`  | DateTime        | no   | UTC, onupdate |

### New table: `broker_fills` (raw idempotency + cursor store)

| Column             | Type          | Null | Notes |
|--------------------|---------------|------|-------|
| `id`               | Integer PK    | no   | |
| `external_exec_id` | String(128)   | no   | **unique** — the broker execution id; the idempotency key |
| `external_order_id`| String(128)   | yes  | parent order id |
| `account`          | String(64)    | yes  | broker account id |
| `symbol`           | String(16)    | no   | uppercased |
| `action`           | String(4)     | no   | `buy` \| `sell` |
| `quantity`         | Integer       | no   | > 0 (contracts in this fill) |
| `price`            | Numeric(18,6) | no   | fill price |
| `fee`              | Numeric(18,4) | no   | fee/commission for this fill (default 0) |
| `executed_at`      | DateTime      | no   | UTC |
| `source`           | String(16)    | no   | `dxtrade` \| `csv` |
| `raw`              | Text          | yes  | original payload (JSON) for audit |
| `ingested_at`      | DateTime      | no   | UTC |
| `processed`        | Boolean       | no   | default false; set true once folded into a trade |
| `trade_id`         | Integer FK    | yes  | →`trades.id`; the round-trip this fill belongs to |

### New table: `sync_state` (single row, id=1)

| Column          | Type        | Null | Notes |
|-----------------|-------------|------|-------|
| `id`            | Integer PK  | no   | always 1 |
| `enabled`       | Boolean     | no   | default false — desired streaming state (worker observes) |
| `status`        | String(16)  | no   | default `'disconnected'` — `disconnected`\|`connecting`\|`streaming`\|`error` |
| `last_cursor`   | String(128) | yes  | last processed execution id / server cursor for replay |
| `last_fill_at`  | DateTime    | yes  | timestamp of most recent processed fill |
| `last_synced_at`| DateTime    | yes  | last successful ingest/heartbeat |
| `last_error`    | Text        | yes  | last error message for UI display |
| `updated_at`    | DateTime    | no   | UTC, onupdate |

All monetary/price fields use `Numeric`/`Decimal` (never float), consistent with Phase 1. Timestamps are naive-UTC (matching `Trade._utcnow`) for identical round-tripping across PostgreSQL and the SQLite test DB.

## Reconciliation Pipeline (core algorithm)

`aggregate_round_trips(fills)` is a **pure function** (no DB, no I/O) so it is exhaustively unit-testable:

1. **Group** fills by `(account, symbol)`; sort each group by `executed_at`, then `external_exec_id` (stable tiebreak).
2. **Walk** each group maintaining signed `position` (buy `+qty`, sell `−qty`) and accumulators for the current round-trip: entry legs (qty, price) and exit legs (qty, price), fee sum, first entry time, last exit time, and the ordered list of constituent `external_exec_id`s.
3. A fill is an **entry** portion when it moves `|position|` away from 0 (same sign as current position, or opens from flat) and an **exit** portion when it moves toward 0. A fill that **crosses 0** is **split**: the portion to 0 closes the current round-trip; the remainder opens the next (with the same fill's price/time, sharing its exec id — recorded on both legs).
4. When `position` returns to **exactly 0**, emit a `RoundTrip`:
   - `side` = `long` if entries were buys else `short`.
   - `contracts` = total entry quantity `Q` (= total exit quantity).
   - `entry_price` = quantity-weighted average of entry legs; `exit_price` = weighted average of exit legs (Decimal, quantized on the trade write).
   - `entry_at` = first entry fill time; `exit_at` = last exit fill time.
   - `fees` = sum of constituent fill fees.
   - `external_id` = stable hash of the sorted constituent exec ids (e.g. `dxt:` + `sha1(",".join(ids))[:24]`).
5. A group ending **non-flat** leaves an **open position** — no trade emitted (Phase 1 = closed trades only); its fills stay `processed=false` and are re-evaluated on the next ingest (when the closing fills arrive).

`ingest_fills(fills, source)` (the impure orchestrator):
1. **Upsert** each `Fill` into `broker_fills` by `external_exec_id` (existing → skip). This is where reconnect/replay duplicates die.
2. Load **all** un-flat-consumed fills for the affected `(account, symbol)` groups (stored fills, not just the new batch, so a late closing fill completes an earlier-opened round-trip).
3. `aggregate_round_trips(...)` → `RoundTrip`s.
4. For each round-trip: resolve tick spec via `instrument.get_spec(symbol)`; if **unknown**, still create the trade with `tick_size`/`tick_value` = 0-placeholder and `review_status='needs_review'` (flagged; P&L shown as pending) — otherwise snapshot the spec, call `compute_pnl`, and set `review_status='ok'`.
5. **Dedupe**: if a trade with this `external_id` exists, update it in place (idempotent); else insert. Link constituent `broker_fills.trade_id` and set `processed=true`.
6. **Manual-overlap flag**: if a `source='manual'` trade matches (symbol, side, contracts, entry/exit price equal, times within tolerance), set the imported trade's `review_status='needs_review'` and `duplicate_of` = the manual trade's id (never delete either).
7. Return `ReconcileResult{ created, updated, skipped_duplicates, flagged, open_positions }`.

`compute_pnl` is **unchanged** and used exactly as in Phase 1 — the whole point of Phase 1's single-source-of-truth convention.

## Backend API

All new routes live under `sync_bp`; thin routes validate with Pydantic, delegate to controllers, return JSON consistent with `errors.py`. `TradeResponse` gains `source`, `external_id`, `review_status`.

- **`GET /api/sync/status`** → `SyncStatusResponse`:
  ```json
  {
    "enabled": true, "status": "streaming",
    "credentials_configured": true,
    "last_synced_at": "2026-07-21T14:05:00Z",
    "last_fill_at": "2026-07-21T14:04:58Z",
    "last_error": null,
    "counts": { "trades_dxtrade": 12, "fills": 40, "needs_review": 1 }
  }
  ```
- **`POST /api/sync/connect`** → sets `sync_state.enabled=true` (desired state; worker picks it up). 200 with status. 400 if credentials not configured.
- **`POST /api/sync/disconnect`** → sets `enabled=false`. 200.
- **`POST /api/sync/credentials`** (`CredentialsPayload`, write-only: `username`, `password`, `domain`, optional `base_url`/`ws_url`) → persists to the gitignored secret store; 204. **Never** echoes the password back; status only exposes `credentials_configured`.
- **`POST /api/sync/import`** (multipart form-data, field `file`) → `CsvStatementSource` → `ingest_fills` → 200 `ReconcileResultResponse`. 400 on unparseable CSV.
- **`POST /api/sync/reconcile`** → `reconcile_all()` over stored fills → 200 `ReconcileResultResponse` (manual backfill / after fixing an instrument spec).
- **`GET /api/instruments`** → `{ "instruments": [InstrumentResponse, ...] }`.
- **`POST /api/sync/_test/ingest`** (**guarded**: only registered when `app.config['TESTING']` or `DEBUG`) → body is a list of fixture fills → runs the real `ingest_fills` with `source='dxtrade'`. Lets the E2E and integration tests drive the automated pipeline deterministically with no network. Returns `ReconcileResultResponse`.

`ReconcileResultResponse`:
```json
{ "created": 2, "updated": 0, "skipped_duplicates": 1, "flagged": 0, "open_positions": 0 }
```

## Streaming Worker Runtime

- **Process**: `worker: python -m app.worker.dxtrade_worker` (Procfile), plus `script/worker` for dev. A single instance; do not scale it horizontally (it owns one broker session).
- **Loop**: create app context → read `sync_state`; if `enabled` and credentials configured → set `status='connecting'`; construct `DXtradeSource` from credentials; on connect, first `fetch_fills(since=last_cursor)` (backfill/replay) → `ingest_fills`; then `async for fill in source.stream_fills(): ingest_fills([fill]); update last_cursor/last_fill_at; status='streaming'`.
- **Reconnect/backoff**: on any disconnect/error → `status='error'`, record `last_error`, exponential backoff (base 1s, cap e.g. 60s, jitter) → retry while still `enabled`. If `enabled` flips false → clean disconnect → `status='disconnected'`.
- **Idempotency across restarts**: because ingestion upserts `broker_fills` by exec id and reconciliation derives a deterministic `external_id`, a restart that re-fetches/re-streams overlapping fills produces **zero** new trades. `last_cursor` narrows the replay window; the raw-fill upsert is the correctness guarantee.
- **Credentials**: read from env / the secret store at connect time; never logged. A credential failure sets `status='error'`, `last_error='authentication failed'`, and stops retrying auth in a tight loop (longer backoff) so a bad password doesn't hammer the broker.
- **No DB coupling to the web tier beyond tables**: the UI polls `/api/sync/status`; there is no in-process shared state.

## Frontend

The `journal` island gains sync capabilities; the manual `TradeForm` and Phase 1 flow are untouched.

- **`ConnectionPanel.tsx`** (rendered above `StatsHeader` in `JournalIsland`):
  - **Status badge**: colored pill — `disconnected` (gray), `connecting` (amber, pulsing), `streaming` (green, "Connected · streaming"), `error` (red, shows `last_error`).
  - **Credentials form**: username / password / domain (+ optional base/ws URLs); submit → `saveCredentials`; password never pre-filled; shows "Credentials configured ✓" from status.
  - **Connect / Disconnect** toggle → `connect` / `disconnect`; disabled while credentials missing.
  - **Import CSV**: file input → `importCsv`; shows the returned `ReconcileResult` summary.
  - **Reconcile** button → `reconcile`; shows summary.
  - **Dedupe visibility**: after any import/reconcile/ingest, render "N imported · M skipped as duplicates · K flagged for review."
- **`SourceBadge.tsx`**: `manual` (neutral) vs `dxtrade` (blue "Auto"); a `needs_review` trade also shows a small "review" chip (with `duplicate_of` tooltip when set).
- **`TradeTable.tsx`**: new **Source** column using `SourceBadge`; review chip on flagged rows.
- **`JournalIsland.tsx`**: hold `syncStatus`; on mount and then on an interval (e.g. every 5s while `enabled`/streaming) call `getSyncStatus`; when the status's `trades_dxtrade` count (or `last_fill_at`) increases, **refetch trades + stats** (reusing the existing `refetch`) so streamed trades appear live. Manual mutations still refetch as in Phase 1.
- **`sync.ts`**: typed wrappers over `/api/sync/*` reusing `api.ts`'s `request`/`ApiRequestError`; `importCsv` builds `FormData` (no JSON content-type).

## Implementation Plan

### Phase 1: Discovery + Foundation
Confirm the DXtrade auth flow and event shapes for Futures Elite (spike, capture fixtures). Add the schema/migration (`source`/`external_id`/review columns + `instruments`/`broker_fills`/`sync_state`), the models, the `instruments` seed, and the `Fill`/`TradeSource` adapter interface with a `StubTradeSource`.

### Phase 2: Core Implementation
Build the reconciliation pipeline (pure aggregation + idempotent ingest + dedupe + manual-overlap flagging) reusing `compute_pnl`; the sync/instrument controllers; the `sync_bp` API (incl. the guarded test-ingest); and the CSV + DXtrade adapters. Then the background worker.

### Phase 3: Integration
Wire the frontend (`ConnectionPanel`, `SourceBadge`, source column, status polling / live refetch), add all tests + fixtures, the automated E2E, run every validation script, and confirm the Phase 1 manual flow and E2E still pass with zero regressions.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### Step 1: Discovery spike — confirm DXtrade auth + capture fixtures
- Research and document (in this spec's Notes or a short `docs/dxtrade-notes.md`) the DXtrade session-auth REST login flow, the Push (WebSocket) subscription for order/position/fill events, the fill/execution event JSON shape, and the REST fills-snapshot endpoint — for a DXtrade deployment matching Futures Elite. Confirm whether programmatic session login is permitted (ToS) or whether the CSV fallback is the primary path.
- Capture **recorded, anonymized** event samples into `tests/fixtures/dxtrade/*.json` and a sample statement into `tests/fixtures/statements/futures_elite_fills.csv`. These drive all tests; **no live connection is used in CI.**
- If the live flow cannot be confirmed, proceed with the CSV path as primary and keep `DXtradeSource` behind the same interface (still fully covered via fixtures).

### Step 2: Extend the `Trade` model + add new models
- Add `source`, `external_id`, `review_status`, `duplicate_of` to `src/app/models/trade.py`.
- Create `src/app/models/instrument.py`, `src/app/models/broker_fill.py`, `src/app/models/sync_state.py`.
- Export all from `src/app/models/__init__.py`.

### Step 3: Create the Alembic migration
- Add `migrations/versions/<rev>_add_source_and_broker_sync.py` with `down_revision = 'a1b2c3d4e5f6'`. `upgrade()`: `op.batch_alter_table('trades')` to add the four columns (with `server_default` then backfill existing rows to `manual`/`ok`) + unique index on `external_id`; `op.create_table` for `instruments`, `broker_fills`, `sync_state`; insert the singleton `sync_state` row (id=1). `downgrade()` reverses in dependency order. Match the existing migration style.

### Step 4: Instruments controller + seed
- Create `src/app/controllers/instrument.py` (`get_spec`, `upsert_instrument`, `list_instruments`, `seed_default_instruments`). Seed common CME futures (ES/MES, NQ/MNQ, CL/MCL, GC/MGC, RTY, YM, 6E, …).
- Update `script/db-seed` to call `seed_default_instruments()` (keep Phase 1 sample trades).

### Step 5: Build the adapter interface + stub source
- Create `src/app/sources/base.py` (`Fill` dataclass, `TradeSource` base, `TradeSourceError`) and `src/app/sources/stub.py` (`StubTradeSource`). Export from `src/app/sources/__init__.py`.

### Step 6: Build the reconciliation pipeline
- Create `src/app/controllers/reconciliation.py`: pure `aggregate_round_trips(fills)` (partial fills, scale in/out, position flips, multiple round-trips), then `ingest_fills(fills, source)` (idempotent raw-fill upsert, aggregate, tick-spec resolution + snapshot, `compute_pnl`, dedupe by `external_id`, manual-overlap flagging) and `reconcile_all()`. Reuse `create_trade`/`compute_pnl` from `controllers/trade.py`. Export from `controllers/__init__.py`.

### Step 7: Sync controller + schemas
- Create `src/app/controllers/sync.py` (state get/set, status recording, credentials store read/write to the gitignored secret file, `import_csv`).
- Create `src/app/schemas/sync.py` (`SyncStatusResponse`, `CredentialsPayload`, `ReconcileResultResponse`, `InstrumentResponse`); add `source`/`external_id`/`review_status` to `TradeResponse`. Export from `schemas/__init__.py`.

### Step 8: Sync API blueprint
- Create `src/app/views/sync.py` (`sync_bp`) with all `/api/sync/*` + `/api/instruments` routes and the **guarded** `/api/sync/_test/ingest` (only when `TESTING`/`DEBUG`). Register `sync_bp` in `src/app/views/__init__.py`.

### Step 9: CSV + DXtrade adapters
- Create `src/app/sources/csv_statement.py` (tolerant column mapping → `Fill`s).
- Create `src/app/sources/dxtrade.py` (`httpx` session-auth REST login, `websockets` Push subscription, event→`Fill`, `fetch_fills(since)`), driven by the Step 1 fixtures in tests.
- Add `websockets` and `httpx` to `requirements.txt`; add `DXTRADE_*`/worker settings to `src/app/config.py` and `.env.example`.

### Step 10: Background streaming worker
- Create `src/app/worker/dxtrade_worker.py` (asyncio loop: app context, honor `enabled`, backfill-then-stream, reconnect/backoff, cursor updates, credential-failure handling). Add the `worker:` line to `Procfile` and a `script/worker` dev launcher. Add the secret-file path to `.gitignore`.

### Step 11: Create the automated E2E test file (early, drives the pipeline)
- Create `e2e/journal-sync.spec.ts` (Playwright): load `/`; POST a fixture fill batch to `/api/sync/_test/ingest` (via `page.request`); assert a new row appears with a **`dxtrade` source badge** and correct server-computed Net P&L; POST the **same batch again** and assert the row count is unchanged (**dedupe holds**) and `skipped_duplicates > 0`; assert the **stats header** reflects the trade. Capture screenshots. Use `--reporter=list` conventions. Do not require any live broker connection.

### Step 12: Frontend — sync client, panel, badges, live refetch
- Create `frontend/src/journal/sync.ts`, `frontend/src/islands/journal/ConnectionPanel.tsx`, `frontend/src/islands/journal/SourceBadge.tsx`.
- Extend `frontend/src/journal/types.ts` (`Trade.source`/`external_id`/`review_status`, `SyncStatus`, `ImportResult`), `TradeTable.tsx` (Source column + review chip), and `JournalIsland.tsx` (status polling + live refetch + render `ConnectionPanel`).

### Step 13: Backend + frontend unit/integration tests
- `tests/test_reconciliation.py` (all edge cases), `tests/test_instrument.py`, `tests/test_csv_import.py`, `tests/test_dxtrade_source.py`, `tests/test_sync_view.py`, `tests/test_worker.py`, with fixtures under `tests/fixtures/dxtrade/` and `tests/fixtures/statements/`.
- `frontend/tests/journal/sync.test.ts`, `frontend/tests/journal/connectionPanel.test.ts`.

### Step 14: Run Validation Commands
- Run `script/test`, `script/typecheck`, `script/lint`, and `script/test-e2e`; fix until all pass with **zero regressions** (Phase 1 manual tests + `e2e/journal.spec.ts` still green).

## Testing Strategy

### Unit Tests
- **`tests/test_reconciliation.py`** — the heart. Pure `aggregate_round_trips` across every fill topology, plus `ingest_fills`/`reconcile_all` idempotency and dedupe, all against fixtures (no network). Assert emitted `RoundTrip` fields and that `compute_pnl` on `(avg_entry, avg_exit, contracts)` matches expected realized dollars.
- **`tests/test_instrument.py`** — `get_spec` hit/miss, seeding idempotency, uppercase normalization.
- **`tests/test_csv_import.py`** — parse a well-formed CSV into `Fill`s and through the pipeline; malformed CSV → 400/`TradeSourceError`.
- **`tests/test_dxtrade_source.py`** — event JSON → `Fill` normalization (buy/sell, qty, price, fee, exec id, time), `stream_fills` yields in order against a fake socket / fixtures; auth-failure raises `TradeSourceError`.
- **`tests/test_sync_view.py`** — status shape; connect/disconnect flip `enabled`; credentials write-only (password never returned); import + reconcile return correct counts; `_test/ingest` runs the pipeline; `TradeResponse` exposes `source`/`external_id`/`review_status`; guarded endpoint absent in production config.
- **`tests/test_worker.py`** — loop with `StubTradeSource` + fake backoff/clock: ingests fixtures, advances cursor, a simulated reconnect re-delivering fills adds zero trades.
- **Frontend `sync.test.ts` / `connectionPanel.test.ts`** — wrappers build correct requests (multipart for CSV), parse status, surface `ApiRequestError`; panel derives the right badge label per status and formats the dedupe summary.

### Edge Cases (must be covered)
- **Partial fills**: one order filled across several executions → one entry leg via weighted average; single round-trip.
- **Scale-in / scale-out**: multiple entries then multiple exits at different prices/sizes → weighted-average entry/exit; `contracts` = total entered; realized dollars exact.
- **Multiple round-trips per symbol/session**: sequence flat→open→flat→open→flat → two distinct trades with distinct `external_id`s.
- **Position flip in one fill**: long 2 then sell 3 → close the long round-trip at the zero-crossing and open a short 1; the crossing fill's exec id appears on both round-trips.
- **Reconnect / duplicate suppression**: re-ingesting the same fills (replay/restart) → `skipped_duplicates` increments, **zero** new trades; `external_id` stable.
- **Symbol with unknown tick spec**: no `instruments` row → trade created `needs_review`, P&L pending, surfaced in UI; a later `reconcile_all()` after seeding the spec fills in P&L in place (same `external_id`).
- **Timezone / UTC**: fills with tz-aware or offset timestamps normalize to naive-UTC; `entry_at ≤ exit_at`; ordering stable.
- **Fees mapping**: per-fill fees sum onto the trade's `fees`; `net_pnl == gross_pnl − fees`; fees on a winning gross can push `net_pnl` negative.
- **Imported trade matching a pre-existing manual trade**: same symbol/side/contracts, equal entry/exit prices, times within tolerance → imported trade flagged `needs_review` + `duplicate_of` set; **neither row deleted**; counts report `flagged`.
- **Empty / failed sync**: no fills → `ReconcileResult` all-zeros, no error; open-only position → `open_positions > 0`, no trade emitted.
- **Credential failure**: bad/absent credentials → `connect` 400 (not configured) or worker `status='error'` + `last_error`; no tight retry loop; no crash.
- **Open position never closed**: fills that never return to flat → no trade; remains pending; completing fills later emit exactly one trade.

### E2E (`e2e/journal-sync.spec.ts`)
Drive the automated flow via the stub/test-ingest endpoint: assert the `dxtrade` source badge, dedupe on double-ingest, and the live stats-header update — with no live prop connection. Keep `e2e/journal.spec.ts` (manual) passing.

## Acceptance Criteria

1. A closed round-trip's fills (from a fixture) ingested through the pipeline produce **exactly one** `trades` row with `source='dxtrade'`, a non-null unique `external_id`, and `net_pnl` matching `compute_pnl` on the weighted-average entry/exit and total contracts.
2. Partial fills, scale-in/out, multiple round-trips, and a position flip each aggregate into the correct number of trades with correct weighted-average prices, contracts, fees, and side (verified by `tests/test_reconciliation.py`).
3. Re-ingesting the same fills (reconnect/restart/replay or a second identical batch) creates **zero** additional trades; `skipped_duplicates` reflects the suppression; `external_id` is stable.
4. An imported trade overlapping a pre-existing **manual** trade is flagged `needs_review` with `duplicate_of` set; **neither** trade is deleted or double-counted in stats beyond what the user chooses.
5. A fill for a symbol with no `instruments` spec creates a `needs_review` trade (P&L pending) surfaced in the UI; after seeding the spec, `reconcile_all()` fills in P&L on the **same** row.
6. Manual entry (Phase 1) is unchanged: manual trades persist with `source='manual'`, `external_id=NULL`, appear alongside imported trades, and the Phase 1 unit tests and `e2e/journal.spec.ts` still pass.
7. The `journal` island shows a connection panel with a live status indicator (disconnected/connecting/streaming/error), a credentials form (password never echoed), Connect/Disconnect, Import CSV, and Reconcile; the trades table shows a **source badge** per row; imports/reconciles show a dedupe summary.
8. The trades table and stats header update live as trades stream in (status polling triggers refetch) with no manual page reload.
9. The background worker runs as a separate `Procfile` process, holds the WebSocket with reconnect/backoff, resumes from its cursor after restart without duplicating, reads credentials from `.env`/the secret store, and never logs the password.
10. The entire feature is exercised in CI with **no live prop connection** (fixtures / stub source / fake socket); `websockets` and `httpx` are declared in `requirements.txt`.
11. `script/test`, `script/typecheck`, `script/lint`, and `script/test-e2e` all pass with zero errors and zero regressions.

## Validation Commands

Execute every command to validate the feature works correctly with zero regressions.

```bash
# Install dependencies (first time; picks up websockets + httpx)
script/bootstrap

# Create .env, database, and run migrations (incl. add_source_and_broker_sync)
script/setup

# Backend + frontend unit tests (pytest + vitest)
script/test

# TypeScript + Python type checking (mypy + tsc)
script/typecheck

# Linting (flake8 + eslint)
script/lint

# End-to-end tests (Playwright; auto-starts dev servers) — runs BOTH
# e2e/journal.spec.ts (manual, Phase 1) and e2e/journal-sync.spec.ts (automated)
script/test-e2e
```

Direct equivalents (from `AGENTS.md`) if a script is unavailable:
```bash
PYTHONPATH=src pytest tests/
cd frontend && npm test
mypy src/ --ignore-missing-imports && cd frontend && npm run typecheck
flake8 src/ tests/ && cd frontend && npm run lint
npx playwright test --reporter=list
```

## Notes

### Conventions honored
- **No decorators for business logic**: reconciliation/sync/instrument controllers and the `TradeSource`/`Fill` classes are plain functions/classes; only Flask route decorators (on `sync_bp`) and Pydantic validators are used, matching Phase 1.
- **`compute_pnl` untouched**: the single source of truth is reused verbatim for both manual and imported trades — the exact extensibility Phase 1's spec promised.
- **Snapshot columns preserved**: imported trades snapshot the resolved instrument tick spec onto `trades`, so historical P&L never silently changes — Phase 1's denormalization rationale, extended.
- **Single-user / no auth**: unchanged; there is one account, one `sync_state` row, all trades global.
- **Numeric/Decimal + naive-UTC** throughout, matching Phase 1's precision and timestamp conventions.

### New dependencies (justified)
- **`websockets`** — pure-Python asyncio WebSocket client for the DXtrade **Push** stream (persistent, reconnecting). Chosen over `websocket-client` because the worker is asyncio-based (one process, one socket, clean backoff via `async`/`await`), and `websockets` is the de-facto standard asyncio client.
- **`httpx`** — async-capable HTTP client for the DXtrade **session-auth REST** login and `fetch_fills(since)` snapshot, so REST and WS share one asyncio loop in the worker. (Sync `requests` would force thread juggling; `httpx` avoids a second concurrency model.)
- **No new frontend dependency** — CSV upload uses `FormData`; status polling uses `fetch`.

### Credential handling & ToS risk (call-out)
- **ToS / legality**: whether Futures Elite's DXtrade deployment permits programmatic/session login outside the browser is **uncertain** and may violate the prop firm's terms. The Step 1 discovery spike must confirm this. The **CSV/statement import** path is the compliant fallback and shares the entire pipeline, so the feature is valuable even if live streaming is disallowed. Ship the CSV path first if in doubt.
- **Credential storage**: passwords live in `.env` or a **gitignored** local secret file written by `/api/sync/credentials`; they are never returned by any API, never logged, and never committed. This is adequate for a single-user tutorial app but is **not** a hardened secret manager — flagged as a known limitation. A real deployment should use OS keyring / a managed secret store.
- **Session/rate limits**: reuse a single broker session; back off aggressively on auth failure so a wrong password never hammers the broker.

### Future work (beyond Phase 2)
- **dxFeed live prices**: subscribe to dxFeed market data to show live/unrealized P&L on open positions and to auto-verify/refresh `instruments` tick specs.
- **Open-position tracking**: a `status` column + unrealized P&L for positions that haven't flattened (Phase 2 only logs closed round-trips).
- **Lot-level (FIFO) matching**: for per-lot / tax reporting, replace weighted-average with matched lots (net dollars unchanged for closed round-trips).
- **Multi-account / multi-broker**: generalize `sync_state` and `broker_fills` to multiple accounts and add more `TradeSource` adapters (Tradovate, Rithmic, IBKR) behind the same interface.
- **Charting & analytics**: equity curve and per-instrument/per-source breakdowns now that trades carry a `source`.
```
