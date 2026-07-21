# Implementation Plan — Trading Journal

## Goal
Auto-populate the journal with the trades the user actually executed at their prop
firm (Futures Elite, on the **DXtrade** platform) in real time, while keeping
Phase 1's manual entry a first-class, coexisting path — with correct tick-based
P&L (reusing `compute_pnl` verbatim) and **no duplicates**.

Sources of truth:
- Phase 1 — spec file `specs/trading-journal-phase1-manual-futures.md` has been
  **removed** from `specs/` (it is fully implemented and re-audited against `src/*`
  below); the shipped code + this plan's "Phase 1 — COMPLETE" section are now the
  reference. Restore the spec from git history (`git show HEAD:specs/...`) if needed.
- Phase 2 — `specs/trading-journal-phase2-dxtrade-automated.md` (only spec on disk)

---

## Phase 1 — COMPLETE (manual futures entry)
> Homepage `GET /` serves the manual futures journal (stats header + add/edit
> form with live P&L preview + editable table), backed by a single `trades`
> table and a RESTful JSON API. Last validated 2026-07-19: 42 pytest + 23 vitest
> + 2 Playwright green; mypy (strict) + tsc + flake8 + eslint clean.
> Re-audited 2026-07-21 against `specs/trading-journal-phase1-manual-futures.md`:
> model (all 19 columns), `compute_pnl`, validation rules, all API routes/status
> codes, all 11 stats fields, and the 6 frontend/island files match the spec with
> no functional gaps. Only nuance: the Phase 1 migration does not set DB-level
> `server_default` for `fees`/`created_at`/`updated_at` (supplied at the ORM layer
> instead) — spec-compliant since the controller is the sole write path. **When
> authoring the Phase 2 migration, keep the same ORM-default convention** for the
> new columns' non-raw-INSERT behavior, but still use `server_default` for the
> backfill/NOT-NULL step as noted below.

Single source of truth for the P&L math: `controllers/trade.py: compute_pnl`
(`ticks` = per-contract signed ticks; contract multiplier applies to dollars
only; `gross_pnl = ticks × tick_value × contracts`; `net_pnl = gross_pnl − fees`).
This is **reused unchanged** by all of Phase 2.

---

## Phase 2 — IN PROGRESS (automated DXtrade fill sync)

### Progress log
- **2026-07-21 — API surface landed (P3: sync controller + schemas + blueprint).**
  Full suite now **77 pytest green** (was 63); mypy(strict)+flake8 clean.
  - **`schemas/sync.py`** — `CredentialsPayload` (write-only, strips+rejects blank
    username/password/domain), `SyncCounts`, `SyncStatusResponse`,
    `ReconcileResultResponse`, `InstrumentResponse`. Exported from `schemas/__init__`.
    `TradeResponse` already had `source`/`external_id`/`review_status`/`duplicate_of`.
  - **`controllers/sync.py`** — `get_sync_state` (creates the id=1 singleton on
    first access so `db.create_all()` test DBs match migrated ones), `set_enabled`
    (desired state only; worker owns `status`), `record_status` (worker→DB writeback,
    sets `last_synced_at` while streaming), `status_counts`
    (trades_dxtrade/fills/needs_review), `load_credentials`/`credentials_configured`/
    `save_credentials` (env is source of truth **per-field**, write-through to the
    gitignored secret file, mode 0600; password never returned), `import_csv`
    (CSV→`ingest_fills(source='csv')`). Exported from `controllers/__init__`.
  - **`views/sync.py`** (`sync_bp`) — `GET /api/sync/status`, `POST connect`
    (400 if creds unconfigured) / `disconnect` / `credentials` (204, no echo) /
    `import` (multipart `file`; 400 on `TradeSourceError`) / `reconcile`,
    `GET /api/instruments`, and the **guarded** `POST /api/sync/_test/ingest`
    attached via `attach_test_routes(app)` **only** when `TESTING`/`DEBUG` (genuinely
    absent → 404 in production). Reuses `journal.py`'s `_validation_error`.
    Registered in `views/__init__.py`.
  - **`config.py`** — added `DXTRADE_SECRET_FILE` (default `.secrets/dxtrade.json`)
    + `DXTRADE_USERNAME/PASSWORD/DOMAIN/BASE_URL/WS_URL` env reads (partial P5 config,
    needed now for credential handling). `.gitignore` now ignores `.secrets/` +
    `dxtrade.json`.
  - **`tests/test_sync_view.py`** (14) — status shape, connect-needs-creds,
    creds write-only + connect/disconnect toggle `enabled`, import counts +
    missing-file/malformed 400, reconcile-after-spec-seed, instruments list,
    `_test/ingest` pipeline + replay-dedupe, non-list 400, **guarded route 404 in
    production config**, status counts reflect ingest, needs_review counted.
  - **Design note:** connect/disconnect write only `sync_state.enabled` (the desired
    state); the worker is the sole writer of `status`. Tests that need a temp secret
    file override `app.config['DXTRADE_SECRET_FILE']` via `tmp_path`.
- **2026-07-21 — Data foundation + core pipeline landed (P0/P1/P2/P4-csv).**
  Migration head is now `b2c3d4e5f6a7_add_source_and_broker_sync` (chains
  `a1b2c3d4e5f6`; applied + reversed cleanly on SQLite). Shipped this increment:
  - **P0 discovery** — `docs/dxtrade-notes.md` written; **ToS risk resolved by
    making the CSV path primary** and keeping `DXtradeSource` fixture-covered but
    unshipped. Fixtures captured under `tests/fixtures/dxtrade/*.json` (7) +
    `tests/fixtures/statements/{futures_elite_fills,malformed}.csv`.
  - **P1 models** — `Trade` gained `source`/`external_id`(unique)/`review_status`/
    `duplicate_of`; new `Instrument`/`BrokerFill`/`SyncState` models; all exported.
  - **P1 migration** — `batch_alter_table` + `server_default` backfill,
    `uq_trades_external_id`, three new tables, singleton `sync_state` row (id=1).
  - **P2 sources** — `sources/base.py` (`Fill`, `TradeSource`, `TradeSourceError`),
    `sources/stub.py` (`StubTradeSource`, `fill_from_dict`), `sources/csv_statement.py`
    (`CsvStatementSource`, tolerant column mapping). `dxtrade.py` NOT built yet.
  - **P2 instruments** — `controllers/instrument.py` (get_spec/upsert/list/seed, 17
    CME/CBOT/NYMEX/COMEX specs); `script/db-seed` seeds them idempotently.
  - **P2 reconciliation** — `controllers/reconciliation.py`: pure
    `aggregate_round_trips` (partial/scale/multi/flip, weighted-avg, fee-split on
    crossing fill), idempotent `ingest_fills`, `reconcile_all`, manual-overlap flag
    (90s tolerance), unknown-spec→needs_review. Reuses `compute_pnl` verbatim;
    builds `Trade` directly (create_trade can't set source/needs_review rows).
  - **Tests** — `test_reconciliation.py` (13), `test_instrument.py` (4),
    `test_csv_import.py` (4). Full suite **63 pytest green**; mypy(strict)+flake8 clean.
  - `TradeResponse` now exposes `source`/`external_id`/`review_status`/`duplicate_of`.
  - **Design note:** imported trades (CSV *or* live) all get `trades.source='dxtrade'`
    (the 2-value column / "Auto" badge); `broker_fills.source` distinguishes the
    ingest channel (`dxtrade`|`csv`).

### Still greenfield (verified 2026-07-21; these remain to build)
- No `src/app/sources/dxtrade.py` (live adapter), no `src/app/worker/`.
- `Procfile` has only `web:`; `requirements.txt` lacks `websockets`/`httpx`;
  `config.py` has `DXTRADE_*` credential settings but **no worker-loop settings**
  (backoff caps etc.); no `script/worker`. (Secret-file path + `.gitignore` DONE.)
- No `e2e/journal-sync.spec.ts` yet (P7; can land now that P3 exists).
- Frontend `journal/types.ts` has no `source`/`review_status`/`SyncStatus` types;
  no `ConnectionPanel.tsx`/`SourceBadge.tsx`/`sync.ts`; `TradeTable`/`JournalIsland`
  not yet source-aware.
- **DONE (this increment):** `controllers/sync.py`, `schemas/sync.py`,
  `views/sync.py` (+ guarded test-ingest), `sync_bp` registered.

### Guiding principles for this build
- **Reuse `compute_pnl` and `create_trade` verbatim** — do not re-implement P&L.
- **Numeric/Decimal + naive-UTC everywhere** (mirror `models/trade.py: _utcnow`,
  `controllers/trade.py: _to_naive_utc`), so SQLite (test) and Postgres (dev)
  round-trip identically.
- **Plain functions/classes, no business-logic decorators** — match Phase 1.
- **Snapshot tick specs onto each `trades` row** so instrument edits never rewrite
  historical P&L.

---

### Prioritized work items (top = do first)

Ordering is dependency-aware and front-loads the highest-value, fully-CI-testable
core (no live broker needed) ahead of the uncertain/risky live-streaming path.

**P0 — De-risk the uncertain path (do before committing to the live adapter)**
- [x] **Discovery spike: confirm DXtrade session-auth + capture fixtures** (spec Step 1).
      DONE 2026-07-21 — `docs/dxtrade-notes.md`; CSV made primary; all 7 dxtrade
      fixtures + 2 statement CSVs captured in normalized `Fill`-dict shape.
      Document (short `docs/dxtrade-notes.md`) the DXtrade session-auth REST login,
      the Push/WebSocket fill-event JSON shape, and the REST fills-snapshot
      endpoint for a Futures-Elite-style deployment. **Confirm whether programmatic
      session login is permitted (ToS).** Capture anonymized fixtures into
      `tests/fixtures/dxtrade/*.json` (simple_round_trip, partial_fills,
      scale_in_out, multiple_round_trips, position_flip, unknown_symbol,
      duplicate_replay) and `tests/fixtures/statements/futures_elite_fills.csv`
      (+ `malformed.csv`). **Risk gate:** if the live flow can't be confirmed or is
      disallowed, make the **CSV path primary** and keep `DXtradeSource` behind the
      same interface (still fixture-covered). Everything downstream is driven by
      these fixtures, so they unblock all tests.

**P1 — Data foundation (unblocks everything)** — ✅ DONE 2026-07-21
- [x] **Extend `Trade` + add new models** (spec Step 2).
      Add `source` (String(16), NOT NULL, default `'manual'`), `external_id`
      (String(128), nullable, unique), `review_status` (String(16), NOT NULL,
      default `'ok'`), `duplicate_of` (Integer FK→`trades.id`, nullable) to
      `models/trade.py`. New models: `models/instrument.py`,
      `models/broker_fill.py`, `models/sync_state.py` (per the spec's column
      tables). Export all from `models/__init__.py`.
- [ ] **Alembic migration `add_source_and_broker_sync`** (spec Step 3),
      `down_revision = 'a1b2c3d4e5f6'`. `op.batch_alter_table('trades')` to add the
      four columns with `server_default` then backfill existing rows to
      `manual`/`ok`; unique index `uq_trades_external_id`; `create_table` for
      `instruments`, `broker_fills`, `sync_state`; insert singleton `sync_state`
      row (id=1). `downgrade()` reverses in dependency order. Match the existing
      migration style; use `batch_alter_table` for SQLite compatibility.

**P2 — The core (pure, exhaustively testable, no network)**
- [ ] **Adapter interface + stub source** (spec Step 5).
      `sources/base.py` (`Fill` dataclass, `TradeSource` base with `stream_fills()`
      async generator + `fetch_fills(since)`, `TradeSourceError`) and
      `sources/stub.py` (`StubTradeSource`, replays fixtures, no network). Export
      from `sources/__init__.py`.
- [ ] **Instruments controller + seed** (spec Step 4).
      `controllers/instrument.py` (`get_spec`, `upsert_instrument`,
      `list_instruments`, `seed_default_instruments`). Seed common CME futures
      (ES/MES, NQ/MNQ, CL/MCL, GC/MGC, RTY, YM, 6E…). Wire
      `seed_default_instruments()` into `script/db-seed` (keep Phase 1 sample trades).
- [ ] **Reconciliation pipeline** (spec Step 6) — *the heart of Phase 2*.
      `controllers/reconciliation.py`: pure `aggregate_round_trips(fills)`
      (weighted-average entry/exit; partial fills, scale-in/out, position-flip
      split at the zero-crossing, multiple round-trips per symbol; open positions
      emit no trade); `ingest_fills(fills, source)` (idempotent `broker_fills`
      upsert by `external_exec_id` → aggregate → tick-spec resolve+snapshot →
      `compute_pnl` → dedupe by deterministic `external_id` → manual-overlap
      flagging via `duplicate_of`); `reconcile_all()`. Reuse `create_trade`/
      `compute_pnl`. Export from `controllers/__init__.py`.

**P3 — API surface + make it drivable (enables integration + E2E)** — ✅ DONE 2026-07-21
- [x] **Sync controller + schemas** (spec Step 7). `controllers/sync.py` +
      `schemas/sync.py` shipped; `TradeResponse` already carried the source fields.
- [x] **`sync_bp` blueprint** (spec Step 8): all routes + guarded `_test/ingest`
      (via `attach_test_routes`, TESTING/DEBUG only) registered in `views/__init__.py`.

**P4 — Value-delivering fallback path (works without a live broker)**
- [ ] **CSV statement adapter** (part of spec Step 9).
      `sources/csv_statement.py` (`CsvStatementSource`, tolerant column mapping,
      stdlib `csv` → `Fill`s). This is the compliant fallback that ships value even
      if live streaming is disallowed — prioritize over the live adapter.

**P5 — Live path (higher risk; gated on the P0 spike)**
- [ ] **DXtrade adapter** (rest of spec Step 9).
      `sources/dxtrade.py` (`httpx` session-auth REST login, `websockets` Push
      subscription, event→`Fill`, `fetch_fills(since)` snapshot). Add `websockets`
      + `httpx` to `requirements.txt`; add `DXTRADE_*`/worker settings to
      `config.py` (as `Config` attrs from env; testing stays SQLite in-memory) and
      `.env.example`.
- [ ] **Background streaming worker** (spec Step 10).
      `worker/dxtrade_worker.py` (asyncio: app context, honor `sync_state.enabled`,
      backfill-then-stream, reconnect/exponential backoff, cursor updates,
      credential-failure long-backoff). Add `worker: python -m app.worker.dxtrade_worker`
      to `Procfile`, a `script/worker` dev launcher, and the secret-file path
      (e.g. `.secrets/dxtrade.json`) to `.gitignore`.

**P6 — Frontend (live UI)**
- [ ] **Sync client + panel + badges + live refetch** (spec Step 12).
      `journal/sync.ts` (typed wrappers over `/api/sync/*` reusing `api.ts`'s
      `request`/`ApiRequestError`; multipart `importCsv`).
      `islands/journal/ConnectionPanel.tsx` (status pill disconnected/connecting/
      streaming/error, credentials form with password never pre-filled,
      Connect/Disconnect, Import CSV, Reconcile, dedupe summary).
      `islands/journal/SourceBadge.tsx` (manual vs dxtrade + review chip).
      Extend `journal/types.ts` (`Trade.source`/`external_id`/`review_status`,
      `SyncStatus`, `ImportResult`), `TradeTable.tsx` (Source column + review
      chip), `JournalIsland.tsx` (poll `/api/sync/status` on interval while
      streaming; refetch trades+stats when `trades_dxtrade`/`last_fill_at`
      increases). `main.ts` unchanged (island already registered).

**P7 — Tests + validation (write alongside each layer; this is the closeout)**
- [ ] **Automated E2E** `e2e/journal-sync.spec.ts` (spec Step 11 — can land early
      once P3 exists): POST a fixture batch to `/api/sync/_test/ingest`, assert a
      `dxtrade` source badge + correct Net P&L, re-POST same batch → row count
      unchanged & `skipped_duplicates > 0`, stats header updates. No live broker.
- [ ] **Backend unit/integration tests** (spec Step 13):
      `test_reconciliation.py` (all edge cases below), `test_instrument.py`,
      `test_csv_import.py`, `test_dxtrade_source.py`, `test_sync_view.py`
      (incl. guarded endpoint absent in production config), `test_worker.py`
      (stub source + fake backoff/clock; reconnect re-delivery adds zero trades).
- [ ] **Frontend tests**: `frontend/tests/journal/sync.test.ts`,
      `connectionPanel.test.ts`.
- [ ] **Run all validation with zero regressions** (spec Step 14):
      `script/test`, `script/typecheck`, `script/lint`, `script/test-e2e` — Phase 1
      unit tests + `e2e/journal.spec.ts` must stay green.

### Edge cases the reconciliation tests MUST cover
Partial fills · scale-in/out (weighted avg) · multiple round-trips per symbol ·
position flip (crossing fill's exec id on both round-trips) ·
reconnect/duplicate suppression (zero new trades, stable `external_id`) ·
unknown tick spec → `needs_review`, filled in by later `reconcile_all()` ·
tz-aware→naive-UTC normalization · per-fill fees summing (net can go negative) ·
imported-overlaps-manual → flagged `needs_review` + `duplicate_of`, neither
deleted · empty/open-only sync → all-zero/`open_positions>0` · credential failure
→ no tight retry loop, no crash.

### Known risks / call-outs
- **ToS/legality of programmatic DXtrade session login is uncertain** (spec
  Decision 7 & Notes). The P0 spike must resolve this; if in doubt, ship the CSV
  path (P4) first and keep the live adapter fixture-covered but unshipped.
- **Credential storage** is `.env` + a gitignored plaintext secret file — adequate
  for a single-user tutorial app, **not** a hardened secret manager. Passwords
  must never be returned by any API or logged.
- **Worker is a single process** — do not scale horizontally (it owns one broker
  session). Correctness across restarts rests on the `broker_fills` upsert +
  deterministic `external_id`, not on the cursor alone.

### Explicitly out of scope (Phase 2)
dxFeed live-price/unrealized P&L · open-position tracking (`status` column) ·
FIFO/lot-level tax matching · multi-account/multi-broker adapters · charting &
analytics. (The data model leaves room for all of these.)
