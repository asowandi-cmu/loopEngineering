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

## Phase 2 — NOT STARTED (automated DXtrade fill sync)

### Gap analysis (re-verified 2026-07-21 against current `src/*`, `frontend/*`, `migrations/*`)
Phase 2 is entirely greenfield — re-confirmed by code search 2026-07-21, nothing
is partially built (migration head is `a1b2c3d4e5f6`, chaining
`f1a2b3c4d5e6`; `TestingConfig` sets `TESTING`+`DEBUG`, `DevelopmentConfig` sets
`DEBUG`, and `ProductionConfig` sets `DEBUG=False` with no `TESTING` — so the
guarded `_test/ingest` route registers in test/dev and is correctly absent in
production. Re-audited independently 2026-07-21: `grep` for
`reconcil|broker_fill|sync_state|instrument|external_id|TradeSource|dxtrade`
across `src/` and `frontend/src/` returns zero matches):
- No `src/app/sources/`, no `src/app/worker/`.
- No `controllers/reconciliation.py`, `controllers/instrument.py`, `controllers/sync.py`.
- No `models/instrument.py`, `models/broker_fill.py`, `models/sync_state.py`; the
  `Trade` model (`models/trade.py`) has **no** `source`/`external_id`/
  `review_status`/`duplicate_of` columns.
- No `views/sync.py`; `views/__init__.py` registers only `journal_bp`.
- Migration head is `a1b2c3d4e5f6_create_trades_table` — this is exactly the
  `down_revision` the Phase 2 migration should chain onto. ✅
- `Procfile` has only a `web:` line (no `worker:`); `requirements.txt` lacks
  `websockets`/`httpx`; `config.py` has no `DXTRADE_*`/worker settings; there is
  no `script/worker`.
- Frontend `journal/types.ts` has no `source`/`review_status`/`SyncStatus`
  types; no `ConnectionPanel.tsx`/`SourceBadge.tsx`/`sync.ts`.

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
- [ ] **Discovery spike: confirm DXtrade session-auth + capture fixtures** (spec Step 1).
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

**P1 — Data foundation (unblocks everything)**
- [ ] **Extend `Trade` + add new models** (spec Step 2).
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

**P3 — API surface + make it drivable (enables integration + E2E)**
- [ ] **Sync controller + schemas** (spec Step 7).
      `controllers/sync.py` (state get/set, status recording, gitignored-secret
      credentials read/write, `import_csv`). `schemas/sync.py`
      (`SyncStatusResponse`, `CredentialsPayload` write-only, `ReconcileResultResponse`,
      `InstrumentResponse`); add `source`/`external_id`/`review_status` to
      `TradeResponse`. Export from `schemas/__init__.py`.
- [ ] **`sync_bp` blueprint** (spec Step 8): `GET /api/sync/status`, `POST
      connect|disconnect|credentials|import|reconcile`, `GET /api/instruments`, and
      the **guarded** `POST /api/sync/_test/ingest` (register only when
      `TESTING`/`DEBUG` — both exist on `TestingConfig`/`DevelopmentConfig`).
      Register in `views/__init__.py` (reuse `journal.py`'s `_validation_error`/
      `_not_found` helpers and `errors.py` content negotiation).

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
