# Implementation Plan — Trading Journal, Phase 1 (Manual Futures Trade Entry)

## Status

> **Overall: 100% Complete — Phase 1 implemented, all validation green.**
> Space Invaders fully removed; the homepage `GET /` now serves the manual
> futures Trading Journal (stats header + add/edit form with live P&L preview +
> editable table) backed by a single `trades` table and a RESTful JSON API.

Spec: `specs/trading-journal-phase1-manual-futures.md` (source of truth).

### Validation (last run 2026-07-19 — all green, zero regressions)
- `script/test` — backend **42 pytest** + frontend **23 vitest** passing.
- `script/typecheck` — mypy (strict, 13 files) + tsc clean.
- `script/lint` — flake8 + eslint clean.
- `script/test-e2e` — **2 Playwright** tests passing (title/mount; add-trade →
  live preview → persisted row `Net P&L = 995.50` → stats header updates).

### What shipped (single source of truth: `controllers/trade.py: compute_pnl`)
- **Model** `src/app/models/trade.py` — `trades` table, all `Numeric`/`Decimal`
  money fields, stored/derived `ticks`/`gross_pnl`/`net_pnl`, server-set
  `created_at`/`updated_at` (naive-UTC helper so SQLite/Postgres round-trip alike).
- **Migration** `migrations/versions/a1b2c3d4e5f6_create_trades_table.py`
  (`down_revision = 'f1a2b3c4d5e6'`). Applied to the dev Postgres DB.
- **Schemas** `src/app/schemas/trade.py` — `TradeCreate`/`TradeUpdate`/
  `TradeResponse`/`StatsResponse`; validators enforce every Phase-1 rule; derived
  fields ignored (`extra='ignore'`); response numerics typed `float` for JSON.
- **Controller** `src/app/controllers/trade.py` — `compute_pnl` + CRUD + SQL
  `compute_stats` (all-zero on empty journal, no divide-by-zero; `_dec` routes
  SQLite float aggregates through `str` to stay exact).
- **View** `src/app/views/journal.py` (`journal_bp`) — `GET /` page + `/api/trades`
  CRUD + `/api/trades/stats`; 400 with `fields` map; 404 JSON. Registered in
  `views/__init__.py`.
- **Template** `src/app/templates/journal.html` — `data-island="journal"` + noscript.
- **Frontend island** `frontend/src/journal/{types,pnl,validation,api,format}.ts`
  and `frontend/src/islands/journal/{index,JournalIsland,StatsHeader,TradeForm,
  TradeTable}.tsx`; `journal` registered in `main.ts`. `pnl.ts` mirrors the
  backend formula exactly (per-contract signed ticks; multiplier on dollars only).
- **Tests** `tests/test_pnl.py`, `tests/test_trade_model.py`,
  `tests/test_journal_view.py` (incl. migrated `TestErrorHandlers`),
  `frontend/tests/journal/{pnl,form}.test.ts`, `e2e/journal.spec.ts`.
- **Housekeeping** `script/db-seed` now seeds sample trades via the controller
  (no longer imports the removed `Hello`). `e2e/*.png` gitignored.

### Key invariant (held identical across backend/frontend/tests)
`ticks` = per-contract signed ticks = `(exit-entry)/tick_size × direction`;
`gross_pnl = ticks × tick_value × contracts`; `net_pnl = gross_pnl - fees`.
ES long 5000→5010, tick 0.25, $12.5/tick, 2 contracts, $4.5 fees → ticks 40,
gross 1000.00, net 995.50 (short 5010→5000 matches; reversing entry/exit flips sign).

### Operational notes
- E2E hits the real dev Postgres DB; `flask db upgrade` (or `script/setup`) must
  have created `trades` first. The add-trade E2E persists a row to the dev DB.
- SQLite (test config) returns `Numeric` as float/Decimal — backend tests assert
  with tolerance.

---

## Out of scope (Phase 2 — not implemented)
Automated broker/CSV import · `instruments` table + auto-fill/fetch · open/running
positions (nullable exit + `status`) · multi-user/auth · charting & analytics.
The Phase-1 design leaves room for all of these (per-trade snapshot columns
survive an instruments table; `compute_pnl` stays the single source of truth).
