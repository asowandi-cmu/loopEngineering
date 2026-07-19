# Implementation Plan — Trading Journal, Phase 1 (Manual Futures Trade Entry)

## Status

> **Overall: 0% Complete — Not started. The entire codebase is still the Space
> Invaders game; the Trading Journal has no backend, frontend, or tests yet.**

Spec: `specs/trading-journal-phase1-manual-futures.md` (comprehensive, self-contained,
includes its own step-by-step and edge-case list — treat it as the source of truth).

**Goal:** Replace the Space Invaders homepage with a manual **futures** Trading
Journal — add/edit/delete/list completed trades with tick-based Decimal P&L, a
server-computed summary-stats header, an add/edit form with a live client-side
P&L preview, and an editable trades table. Persistence is one `trades` table
(SQLAlchemy 2 + Alembic); the UI is a new `journal` React Island on `GET /`.

**Scope guardrails (per spec):** Phase 1 = completed/closed trades only (exit
fields required). No auth (single-user, global trades). No charts. Phase 2
(broker import, `instruments` table, open positions, multi-user, analytics) is
explicitly **out of scope** — do not build it.

### Research findings (verified 2026-07-19)
- Prior plan was 100% stale (described the shipped Space Invaders feature). Rewritten.
- Nothing from the trading journal exists yet: no `Trade` model, no `trades`
  migration, no schemas/controllers content, no `journal` view/template/island, no
  journal tests. `src/app/schemas/__init__.py` and `controllers/__init__.py` are
  empty scaffolds (`__all__ = []`).
- All reference patterns the spec relies on exist and match: `register_blueprints`
  (`views/__init__.py`), `db`/`Base` (`models/base.py`), content-negotiated error
  handlers with `wants_json_response` (`errors.py`), the island registry + `mount()`
  contract (`main.ts`, `islands/game/index.tsx`), `base.html`, and `conftest.py`
  (SQLite in-memory, `db.create_all()`/`drop_all()` per test).
- **Migration head is `f1a2b3c4d5e6`** (`drop_hello_table`) → new migration's
  `down_revision` must be `'f1a2b3c4d5e6'`. Confirmed via revision chain.
- **Pydantic 2.13.4 is installed** and in `requirements.txt`. No new deps required.
- `TestingConfig` uses `sqlite:///:memory:`; `Numeric` round-trips as `Decimal`/float
  under SQLite — assert with tolerance in tests.
- `script/db-seed` still imports the removed `Hello` model (already broken) — fix as housekeeping.
- No `src/lib/` directory exists; the spec does not require one. `src/app/models|schemas|controllers|views`
  are the shared layers to build within — put the P&L math once in `controllers/trade.py`.
- **One convention to hold identical across backend/frontend/tests:** `ticks` =
  *per-contract* signed ticks = `(exit-entry)/tick_size × direction`; the contract
  multiplier applies to **dollars only** (`gross_pnl = ticks × tick_value × contracts`).

---

## Prioritized tasks (yet to be implemented, dependency-ordered)

### P0 — Foundation: remove Space Invaders, scaffold data + backend core
- [ ] **Remove Space Invaders backend/homepage wiring:** delete `src/app/views/game.py`,
      `src/app/templates/game.html`, `tests/test_game_view.py` (preserve its
      `TestErrorHandlers` cases — move into the new `tests/test_journal_view.py` or a
      shared `tests/test_errors.py`); remove the `game_bp` import/registration in
      `src/app/views/__init__.py` (temporarily leaving no blueprint until `journal_bp`).
- [ ] **Remove Space Invaders frontend/tests:** delete `frontend/src/game/` (9 files),
      `frontend/src/islands/game/`, `frontend/tests/game/`, `e2e/game.spec.ts`; remove
      the `game` entry from `islandRegistry` in `frontend/src/main.ts`. Update the
      Space-Invaders-specific comment in `frontend/src/types/index.ts` (keep `IslandProps`).
- [ ] **`Trade` model** (`src/app/models/trade.py`): all columns per the spec's Data Model
      table — `Numeric`/`Decimal` for every money/price field, required exit fields,
      server-set `created_at`/`updated_at`, stored/derived `ticks`/`gross_pnl`/`net_pnl`.
      Export from `src/app/models/__init__.py` (add to `__all__`).
- [ ] **Alembic migration** `create_trades_table` with `down_revision = 'f1a2b3c4d5e6'`;
      `upgrade()` creates `trades`, `downgrade()` drops it. Match the existing hello-migration
      style; verify column types/nullability/scales against the spec table before committing.
- [ ] **Pydantic schemas** (`src/app/schemas/trade.py`): `TradeCreate`, `TradeUpdate`,
      `TradeResponse`, `StatsResponse` with validators — `tick_size > 0`, `tick_value > 0`,
      `contracts ≥ 1`, prices `≥ 0`, `fees ≥ 0` (default 0), `side ∈ {long, short}`,
      `exit_at ≥ entry_at`, exit fields required; ignore/reject client-supplied derived
      fields. Export from `src/app/schemas/__init__.py`.
- [ ] **Controller** (`src/app/controllers/trade.py`, plain functions, no decorators):
      `compute_pnl(...)` as the single Decimal source of truth, plus `create_trade`,
      `update_trade`, `delete_trade`, `get_trade`, `list_trades`, `compute_stats`.
      `create_trade`/`update_trade` always recompute and persist the derived columns;
      `compute_stats` aggregates in SQL and returns all-zero (no divide-by-zero) for an
      empty journal. Export from `src/app/controllers/__init__.py`.

### P1 — API + homepage route
- [ ] **`journal_bp` view** (`src/app/views/journal.py`): `GET /` renders `journal.html`;
      JSON API `GET/POST /api/trades`, `GET/PUT/DELETE /api/trades/<int:trade_id>`,
      `GET /api/trades/stats`. Thin routes: validate via schemas, delegate to the controller,
      return correct status codes (201/200/204/400/404). Validation → 400 JSON with a `fields`
      map; missing rows → 404 JSON (consistent with `errors.py`). Register in `views/__init__.py`.
- [ ] **Homepage template** (`src/app/templates/journal.html`): extends `base.html`, title
      "Trading Journal", `<h1>`, `<div data-island="journal">` with a `<noscript>` fallback
      (mirror `game.html` structure/Tailwind usage).

### P2 — Frontend `journal` island
- [ ] **Island core + registry:** `frontend/src/journal/types.ts` (`Trade`, `TradeInput`,
      `Stats`, `Side`), `frontend/src/journal/pnl.ts` (pure `computeTicks`, `computeGrossPnl`,
      `computeNetPnl`, `computePreview` mirroring the backend formula; `tick_size ≤ 0 → null`),
      `frontend/src/journal/api.ts` (typed fetch wrappers exposing parsed `{ message, fields }`).
      Add `journal: () => import('./islands/journal')` to `islandRegistry` in `main.ts`.
- [ ] **Island entry + owner:** `frontend/src/islands/journal/index.tsx` (`mount` clears
      fallback, `createRoot().render(<JournalIsland />)`) and `JournalIsland.tsx`
      (fetch-on-mount `Promise.all([listTrades(), getStats()])`; hold `trades`/`stats`/`editingId`/`loading`/`error`;
      refetch after every mutation; clear form/edit state).
- [ ] **UI components:** `StatsHeader.tsx` (Total Net P&L colored by sign, Win Rate %,
      # Trades, Avg Win, Avg Loss, Total Ticks — numbers only), `TradeForm.tsx` (controlled
      inputs, live `computePreview` P&L, client validation mirroring backend rules, surfaces
      API 400 `fields` inline, add + edit modes with "Cancel edit"), `TradeTable.tsx`
      (columns per spec, Edit loads form, Delete confirms, empty state).

### P3 — Tests + validation (gate on green)
- [ ] **Backend `tests/test_pnl.py`:** `compute_pnl` across long/short, multi-contract, fees,
      fractional ticks, Decimal precision.
- [ ] **Backend `tests/test_trade_model.py`:** persistence + derived-column correctness;
      assert `net_pnl == gross_pnl - fees`; `Numeric` round-trips (tolerance under SQLite).
- [ ] **Backend `tests/test_journal_view.py`:** `GET /` shell (200, title, `data-island="journal"`);
      full CRUD (201/list/one/PUT-recomputes/DELETE 204→404); stats on empty + populated;
      validation 400s with `fields`; 404s; **plus the migrated `TestErrorHandlers` cases**.
- [ ] **Frontend `frontend/tests/journal/pnl.test.ts`:** `pnl.ts` vs backend cases
      (long/short, fractional, `tick_size ≤ 0 → null`, multi-contract).
- [ ] **Frontend `frontend/tests/journal/form.test.ts`:** form-validation helpers reject
      `tick_size ≤ 0`, `contracts < 1`, `exit < entry`, missing exit; accept valid input.
- [ ] **E2E `e2e/journal.spec.ts`:** load `/`; assert title + mount; fill the known ES long
      trade (5000→5010, tick 0.25, tick_value 12.5, 2 contracts, fees 4.5); assert live preview
      ticks/net; submit; assert new row `Net P&L = 995.50` and Stats header updates; screenshot.
      Use `--reporter=list` (per AGENTS.md).
- [ ] **Run all validation:** `script/test`, `script/typecheck`, `script/lint`, `script/test-e2e`
      (or the direct equivalents) — fix until all green with zero regressions.

### P4 — Housekeeping (non-blocking)
- [ ] **`script/db-seed`:** stop importing the removed `Hello` model; optionally seed 2–3
      sample trades via the controller so it runs cleanly.

---

## Edge cases that must be covered (from spec — do not drop)
Short trade sign flip · zero tick_size → 400 / `pnl.ts` null · negative tick_size → 400 ·
fractional ticks stored with precision · large contract counts (e.g. 1000) no overflow ·
missing exit price → 400 · `contracts < 1` → 400 · negative prices → 400 · `exit_at < entry_at`
→ 400 · fees > gross → net negative · scratch trade (`net_pnl == 0`) counts as neither win nor
loss · empty-journal stats all zeros, no divide-by-zero.

## Acceptance (summary — full list in spec §Acceptance Criteria)
`/` renders the journal (no Space Invaders) · add/edit/delete works and persists · long ES
example → ticks 40 / gross 1000.00 / net 995.50 (short equivalent matches; reversing entry/exit
flips sign) · live preview updates before submit · stats header derives from stored trades and
updates after mutations · API 400 `fields` map for all invalid inputs · empty-journal stats all
zeros · tick-based Decimal math identical backend/frontend · all four validation scripts green.

## Out of scope (Phase 2 — do not implement)
Automated broker/CSV import · `instruments` table + auto-fill/fetch · open/running positions
(nullable exit + `status`) · multi-user/auth · charting & analytics.
