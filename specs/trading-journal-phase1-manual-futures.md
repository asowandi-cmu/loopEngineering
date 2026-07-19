# Feature: Trading Journal — Phase 1 (Manual Futures Trade Entry)

> Spec ID: `trading-journal-phase1-manual-futures`
> Scope: **Phase 1 only** — manual add/edit/delete/list of completed **futures** trades with computed tick-based P&L and a summary-stats header. Automated import/sync is **Phase 2 (out of scope; noted as future work only)**.

## Feature Description

Replace the current homepage feature (a client-side Space Invaders game, which itself replaced a Hello World CRUD demo) with a **Trading Journal** for **futures contracts only**.

A single user (no authentication — all trades are global, matching this tutorial repo's conventions) manually records completed futures trades. For each trade the user manually enters the instrument's **tick size** and **tick value (USD per tick)** — these are NOT auto-fetched (auto-fetch is Phase 2). The system computes, from ticks:

- `ticks_moved = (exit_price - entry_price) / tick_size`
- `gross_pnl = ticks_moved × tick_value × contracts × direction` where `direction = +1` (long) or `-1` (short)
- `ticks` (first-class, signed so positive = ticks gained) `= ticks_moved × direction`
- `net_pnl = gross_pnl - fees`

The homepage becomes a full-page journal: a **summary stats header** (total net P&L, win rate, number of trades, average win, average loss, total ticks), an **add-trade form** with a **live P&L preview** that recomputes as the user types, and an **editable trades table** supporting edit and delete. Persistence is a single PostgreSQL table via SQLAlchemy 2 + Alembic. The backend exposes a small RESTful JSON API; the frontend is a new React Island (`journal`) mounted on the homepage.

## User Story

As a **futures trader keeping a manual trading journal**
I want to **record each completed trade (instrument, side, contracts, entry/exit prices, tick size, tick value, fees) and see computed ticks and P&L plus running summary stats**
So that **I can track my performance (net P&L, win rate, ticks gained/lost) without a spreadsheet, and later graduate to automated broker import (Phase 2).**

## Problem Statement

The homepage currently hosts a Space Invaders game that has served its demonstration purpose. There is no way to record or analyze trading activity. Futures P&L is not a simple `exit - entry` price difference: it depends on the instrument's tick size and dollar-per-tick value, which vary per contract (ES, NQ, CL, GC, …). Traders need a reliable, repeatable way to enter completed trades and have ticks and dollar P&L computed correctly and consistently, with at-a-glance summary statistics.

## Solution Statement

Build a manual futures Trading Journal on top of the existing Flask 3 + React Islands architecture:

- **Data**: one `trades` table. Each row stores the raw trade inputs (including per-trade `tick_size` and `tick_value`) **and** the derived values (`ticks`, `gross_pnl`, `net_pnl`) as **denormalized, stored** columns computed at write time by a single pure function. (Rationale below.)
- **Backend**: a `Trade` SQLAlchemy model, Pydantic schemas for request validation, a plain-function controller layer holding the P&L math and CRUD/stats logic (no decorators for business logic per `AGENTS.md`), and a `journal_bp` blueprint that serves the homepage HTML shell and a RESTful JSON API (`/api/trades` CRUD + `/api/trades/stats`).
- **Frontend**: a new `journal` React Island rendering a stats header, an add/edit form with a live client-side P&L preview (a pure `pnl.ts` helper mirroring the backend formula), and an editable trades table. Wired into `islandRegistry` in `main.ts` and mounted from a new `journal.html` template on `GET /`.
- **Removal**: delete all Space Invaders backend/frontend/test files and repurpose the homepage route.
- **Testing**: pytest for the model, API and P&L math (with the required edge cases), Vitest for the P&L helper and form validation, and a Playwright E2E that adds a trade and asserts the computed P&L and updated stats.

### Key design decisions (recommended, with justification)

**1. Store computed P&L/ticks (denormalized) vs compute on read → RECOMMENDATION: store them (computed at write time).**
The `trades` row stores `ticks`, `gross_pnl`, and `net_pnl` as columns, written by the controller via one shared pure function on create/update.
- *Why:* (a) the stats endpoint aggregates in SQL (`SUM`, `COUNT`, `AVG`) directly over stored columns — no per-row Python recomputation; (b) each row is a stable snapshot alongside the exact inputs (`tick_size`, `tick_value`) used, so historical rows never silently change; (c) the frontend renders authoritative values without re-deriving them.
- *Tradeoff / mitigation:* denormalized values can drift from inputs if edited out-of-band. Mitigation: **the only write path is the controller**, which always recomputes derived columns from inputs on every create/update; there is no API to set `ticks`/`gross_pnl`/`net_pnl` directly (they are response-only). A test asserts `net_pnl == gross_pnl - fees` and matches the formula.

**2. Per-trade tick size/value vs a separate `instruments` table → RECOMMENDATION: per-trade columns (Phase 1).**
`tick_size` and `tick_value` are stored on each trade row and entered manually per trade.
- *Why:* it is the simplest schema that still computes P&L reliably and self-containedly, and it matches the hard requirement of "manual per-tick input by the customer." No joins, no seed data, no instrument-management UI.
- *Tradeoff:* the same instrument's tick spec is duplicated across its trades and could be entered inconsistently (e.g. one ES trade with tick_value 12.50, another with 50.00). This is acceptable for a single-user manual journal. **Phase 2** can introduce an `instruments` table (symbol → tick_size, tick_value, exchange) with auto-fill/auto-fetch, and `trades` can keep the per-trade snapshot columns for historical accuracy.

**3. Stats server-side endpoint vs client-side → RECOMMENDATION: server-side `GET /api/trades/stats`.**
- *Why:* single source of truth for the aggregation formulas, consistent with stored P&L, and it scales past what's convenient to recompute in the browser. The client still keeps a pure `pnl.ts` for the **live form preview only** (a single prospective trade), not for the persisted stats.

**4. Phase 1 = completed (closed) trades only.**
Every trade has required exit fields; the API **rejects** a trade with a missing exit price. Open/running positions are **future work** (a nullable exit + `status` column). This keeps the schema and P&L unambiguous and satisfies the "missing exit price rejected" edge case.

**5. Money/price precision:** use SQLAlchemy `Numeric` (not float) for all prices, tick sizes, tick values, fees, and P&L to avoid binary-float rounding errors in financial math. Serialize to JSON as numbers/strings consistently (see API shapes).

## Relevant Files

Use these files to implement the feature:

**Backend — modify**
- `src/app/views/__init__.py` — swap `game_bp` registration for `journal_bp`.
- `src/app/models/__init__.py` — export the new `Trade` model (so Alembic autogenerate/`db.create_all()` sees it and tests can import it).
- `src/app/config.py` — no change expected; testing config already uses SQLite in-memory. Verify `Numeric` behaves under SQLite for tests (it does; values come back as `Decimal`/float — assert with tolerance).
- `script/db-seed` — currently imports a non-existent `Hello` model and is already broken; update it to seed a couple of sample trades (or leave a clear TODO). Non-blocking for the feature but should not stay referencing `Hello`.

**Backend — remove**
- `src/app/views/game.py` — replaced by `src/app/views/journal.py`.
- `src/app/templates/game.html` — replaced by `src/app/templates/journal.html`.
- `tests/test_game_view.py` — replaced by `tests/test_journal_view.py` (preserve the `TestErrorHandlers` cases by moving them into the new test module or a shared `tests/test_errors.py`).

**Backend — reference (patterns to follow, do not rewrite)**
- `src/app/__init__.py` — app factory; blueprints registered via `register_blueprints`.
- `src/app/models/base.py` — shared `db = SQLAlchemy(model_class=Base)`; models inherit `db.Model`.
- `src/app/errors.py` — content-negotiated JSON/HTML error handlers (`wants_json_response`, 400/404/500). API validation errors should surface as JSON.
- `migrations/versions/e31396db40b1_create_hello_table.py` and `migrations/versions/f1a2b3c4d5e6_drop_hello_table.py` — Alembic migration style (`op.create_table`, revision chaining). New migration's `down_revision` must chain onto the latest head (`f1a2b3c4d5e6`).
- `tests/conftest.py` — `app`/`client` fixtures; SQLite in-memory; `db.create_all()`/`drop_all()` per test.

**Frontend — modify**
- `frontend/src/main.ts` — replace the `game` entry in `islandRegistry` with `journal: () => import('./islands/journal')`.
- `frontend/src/types/index.ts` — keep `IslandProps`; may add nothing (journal types live in `frontend/src/journal/types.ts`).

**Frontend — remove**
- `frontend/src/game/Alien.ts`, `AlienGrid.ts`, `Bullet.ts`, `InputHandler.ts`, `Player.ts`, `Renderer.ts`, `SpaceInvaders.ts`, `constants.ts`, `types.ts` (entire `frontend/src/game/` directory).
- `frontend/src/islands/game/index.tsx`, `frontend/src/islands/game/GameIsland.tsx` (entire `frontend/src/islands/game/` directory).
- `frontend/tests/game/SpaceInvaders.test.ts`, `frontend/tests/game/entities.test.ts` (entire `frontend/tests/game/` directory).

**Tests — remove**
- `e2e/game.spec.ts` — replaced by `e2e/journal.spec.ts`.

### New Files

**Backend**
- `src/app/models/trade.py` — `Trade` SQLAlchemy 2 declarative model (columns below).
- `src/app/schemas/trade.py` — Pydantic v2 schemas: `TradeCreate`, `TradeUpdate`, `TradeResponse`, `StatsResponse`, plus field validators (tick_size > 0, contracts > 0, prices ≥ 0, tick_value > 0, fees ≥ 0, exit_at ≥ entry_at, side ∈ {long, short}).
- `src/app/controllers/trade.py` — plain functions (no decorators): `compute_pnl(...)` (the single P&L source of truth), `create_trade`, `update_trade`, `delete_trade`, `get_trade`, `list_trades`, `compute_stats`.
- `src/app/views/journal.py` — `journal_bp` blueprint: `GET /` (page) + JSON API routes delegating to the controller.
- `src/app/templates/journal.html` — extends `base.html`; `<div data-island="journal">` mount point; title "Trading Journal".
- `migrations/versions/<rev>_create_trades_table.py` — Alembic migration creating `trades` (chained onto the current head).

**Frontend**
- `frontend/src/islands/journal/index.tsx` — island `mount(element, props)` entry.
- `frontend/src/islands/journal/JournalIsland.tsx` — top-level component: fetches trades + stats, holds state, renders `StatsHeader` + `TradeForm` + `TradeTable`.
- `frontend/src/islands/journal/StatsHeader.tsx` — summary stats display.
- `frontend/src/islands/journal/TradeForm.tsx` — add/edit form with live P&L preview.
- `frontend/src/islands/journal/TradeTable.tsx` — editable/deletable trades table.
- `frontend/src/journal/pnl.ts` — pure P&L helper (`computeTicks`, `computeGrossPnl`, `computeNetPnl`, `computePreview`) mirroring the backend formula.
- `frontend/src/journal/types.ts` — `Trade`, `TradeInput`, `Stats`, `Side` TypeScript types.
- `frontend/src/journal/api.ts` — typed `fetch` wrappers (`listTrades`, `createTrade`, `updateTrade`, `deleteTrade`, `getStats`).

**Tests**
- `tests/test_journal_view.py` — page route + JSON API + error-handler tests.
- `tests/test_trade_model.py` — model persistence + stored-column correctness.
- `tests/test_pnl.py` — P&L math edge cases (backend).
- `frontend/tests/journal/pnl.test.ts` — Vitest for the P&L helper.
- `frontend/tests/journal/form.test.ts` — Vitest for form validation logic.
- `e2e/journal.spec.ts` — Playwright E2E: add a trade, assert computed P&L + stats update.

## Data Model / Migration Plan

### Table: `trades`

| Column         | Type                 | Null | Default   | Notes |
|----------------|----------------------|------|-----------|-------|
| `id`           | Integer, PK          | no   | auto      | primary key |
| `symbol`       | String(16)           | no   |           | futures root symbol, e.g. `ES`, `NQ`, `CL`, `GC`; store uppercased/trimmed |
| `product_name` | String(120)          | yes  | NULL      | optional human name, e.g. "E-mini S&P 500" |
| `side`         | String(5)            | no   |           | `long` or `short` (app-level check; keep as string for portability) |
| `contracts`    | Integer              | no   |           | number of contracts; must be > 0 |
| `entry_price`  | Numeric(18, 6)       | no   |           | ≥ 0 |
| `exit_price`   | Numeric(18, 6)       | no   |           | ≥ 0 (required — Phase 1 is closed trades only) |
| `tick_size`    | Numeric(18, 8)       | no   |           | must be > 0 (e.g. 0.25 for ES) |
| `tick_value`   | Numeric(18, 4)       | no   |           | USD per tick, must be > 0 (e.g. 12.50 for ES) |
| `entry_at`     | DateTime             | no   |           | entry timestamp |
| `exit_at`      | DateTime             | no   |           | exit timestamp; must be ≥ `entry_at` |
| `fees`         | Numeric(18, 4)       | no   | 0         | total fees + commissions for the trade, ≥ 0 |
| `ticks`        | Numeric(18, 4)       | no   |           | **stored/derived**: signed ticks gained (positive = gain) |
| `gross_pnl`    | Numeric(18, 4)       | no   |           | **stored/derived**: gross dollar P&L before fees |
| `net_pnl`      | Numeric(18, 4)       | no   |           | **stored/derived**: `gross_pnl - fees` |
| `strategy`     | String(80)           | yes  | NULL      | optional setup/strategy tag |
| `notes`        | Text                 | yes  | NULL      | optional free-text |
| `created_at`   | DateTime             | no   | now (UTC) | server-set |
| `updated_at`   | DateTime             | no   | now (UTC) | server-set, updated on edit |

Notes:
- Use `Numeric`/`Decimal` throughout for financial fields. `ticks` uses scale 4 to represent fractional ticks; whole-tick trades store e.g. `40.0000`.
- `ticks`, `gross_pnl`, `net_pnl` are **never accepted from the client**; the controller computes and writes them on every create/update.
- `side` kept as a plain `String` with an application-level validator (Pydantic) rather than a DB enum, to keep the migration simple and portable across PostgreSQL and the SQLite test DB.

### Migration task
- Generate a new Alembic revision `create_trades_table` whose `down_revision = 'f1a2b3c4d5e6'` (the current head — the `drop_hello_table` revision). `upgrade()` calls `op.create_table('trades', ...)` with the columns above; `downgrade()` calls `op.drop_table('trades')`. Follow the style of the existing hello migrations. Either hand-write the migration or run `flask db migrate` and adjust — but verify column types/nullability match this table before committing.

## Backend API

Base: JSON over the existing Flask app. All API routes live under `journal_bp`. Business logic is in `controllers/trade.py` as plain functions; routes are thin. Validation errors return HTTP 400 with a JSON body; not-found returns 404 JSON (consistent with `errors.py`).

### Page route
- `GET /` → renders `journal.html` (HTML shell with `data-island="journal"`). Title "Trading Journal".

### JSON API

**`GET /api/trades`** — list all trades, newest first (`ORDER BY entry_at DESC, id DESC`).
- 200 → `{ "trades": [TradeResponse, ...] }`

**`POST /api/trades`** — create a trade.
- Request body `TradeCreate` (JSON):
  ```json
  {
    "symbol": "ES",
    "product_name": "E-mini S&P 500",
    "side": "long",
    "contracts": 2,
    "entry_price": 5000.00,
    "exit_price": 5010.00,
    "tick_size": 0.25,
    "tick_value": 12.50,
    "entry_at": "2026-07-19T13:30:00Z",
    "exit_at": "2026-07-19T14:05:00Z",
    "fees": 4.50,
    "strategy": "ORB",
    "notes": "clean breakout"
  }
  ```
- 201 → `TradeResponse` (includes computed `ticks`, `gross_pnl`, `net_pnl`).
- 400 → `{ "error": "Bad Request", "message": "...", "fields": { "tick_size": "must be greater than 0" } }` on validation failure.

**`GET /api/trades/<int:trade_id>`** — fetch one.
- 200 → `TradeResponse`; 404 if missing.

**`PUT /api/trades/<int:trade_id>`** — full update (recomputes derived columns).
- Request body `TradeUpdate` (same fields as create; all required for a full replace). 200 → updated `TradeResponse`; 400 on validation; 404 if missing.

**`DELETE /api/trades/<int:trade_id>`** — delete.
- 204 (no body); 404 if missing.

**`GET /api/trades/stats`** — summary statistics over all trades.
- 200 → `StatsResponse`:
  ```json
  {
    "num_trades": 12,
    "total_net_pnl": 812.50,
    "total_gross_pnl": 866.50,
    "total_fees": 54.00,
    "total_ticks": 173.0,
    "wins": 8,
    "losses": 3,
    "scratches": 1,
    "win_rate": 0.6667,
    "average_win": 145.20,
    "average_loss": -88.30
  }
  ```
- Empty journal (0 trades) → zeros; `win_rate`, `average_win`, `average_loss` return `0` (never divide by zero).

### `TradeResponse` shape
All persisted columns plus derived values; datetimes as ISO-8601 strings; numeric fields serialized as JSON numbers (round to sensible scale). Example:
```json
{
  "id": 1, "symbol": "ES", "product_name": "E-mini S&P 500", "side": "long",
  "contracts": 2, "entry_price": 5000.0, "exit_price": 5010.0,
  "tick_size": 0.25, "tick_value": 12.5,
  "entry_at": "2026-07-19T13:30:00Z", "exit_at": "2026-07-19T14:05:00Z",
  "fees": 4.5, "ticks": 80.0, "gross_pnl": 1000.0, "net_pnl": 995.5,
  "strategy": "ORB", "notes": "clean breakout",
  "created_at": "2026-07-19T14:06:00Z", "updated_at": "2026-07-19T14:06:00Z"
}
```
(For `contracts=2`, long, entry 5000→5010, tick 0.25, tick_value 12.5: ticks_moved = 40; ticks = +40 per contract → the response's `ticks` is signed ticks gained. **Define `ticks` as per-contract signed ticks** = `(exit-entry)/tick_size × direction = 40`; `gross_pnl = 40 × 12.5 × 2 = 1000`. Keep `ticks` as per-contract movement so it reads as "the trade moved 40 ticks in my favor"; `total_ticks` in stats is the sum of these per-trade `ticks`. **Implementers must pick one convention and keep backend + frontend + tests identical** — this spec's convention: `ticks` = per-contract signed ticks; contract multiplier applies only to dollars.)

### Validation rules (Pydantic `TradeCreate`/`TradeUpdate`)
- `symbol`: non-empty after trim; length ≤ 16; store uppercased.
- `side`: must be exactly `"long"` or `"short"`.
- `contracts`: integer ≥ 1.
- `entry_price`, `exit_price`: `Decimal` ≥ 0.
- `tick_size`: `Decimal` > 0 (reject 0 and negatives).
- `tick_value`: `Decimal` > 0.
- `fees`: `Decimal` ≥ 0; default 0 if omitted.
- `entry_at`, `exit_at`: valid datetimes; `exit_at` ≥ `entry_at`.
- `exit_price` and `exit_at` are **required** (missing exit → 400). Reject unknown/derived fields (`ticks`, `gross_pnl`, `net_pnl` in the request are ignored or rejected).

### P&L function (single source of truth — `controllers/trade.py: compute_pnl`)
```
direction = +1 if side == "long" else -1
ticks_moved = (exit_price - entry_price) / tick_size      # signed by price
ticks       = ticks_moved * direction                     # signed by P&L (per contract)
gross_pnl   = ticks * tick_value * contracts
net_pnl     = gross_pnl - fees
```
Compute with `Decimal` to preserve precision; quantize on write to the column scales. This exact formula is mirrored in `frontend/src/journal/pnl.ts` for the live preview.

## Frontend

New React Island `journal`, mounted on the homepage.

**`journal.html`** (new template): extends `base.html`, title "Trading Journal", a centered `<main>` with an `<h1>Trading Journal</h1>` and `<div data-island="journal">` containing a `<noscript>` fallback.

**`main.ts`**: `islandRegistry = { journal: () => import('./islands/journal') }` (game entry removed).

**`islands/journal/index.tsx`**: `mount(element, _props)` clears fallback, `createRoot(element).render(<JournalIsland />)` (mirror the existing island contract).

**`JournalIsland.tsx`** (state owner):
- On mount, `Promise.all([listTrades(), getStats()])`; hold `trades`, `stats`, `editingId`, `loading`, `error` in state.
- Renders `<StatsHeader stats={stats} />`, `<TradeForm ... />`, `<TradeTable ... />`.
- After any create/update/delete, refetch trades + stats (simplest correct approach) and clear the form/edit state.

**`StatsHeader.tsx`**: renders tiles/row for Total Net P&L, Win Rate (%), # Trades, Average Win, Average Loss, Total Ticks. Color net P&L green/red by sign. Numbers only — **no heavy charting** (charts are future work).

**`TradeForm.tsx`** (add + edit):
- Controlled inputs for all `TradeInput` fields (symbol, product_name, side select, contracts, entry_price, exit_price, tick_size, tick_value, entry_at, exit_at, fees, strategy, notes).
- **Live P&L preview**: as the user types, call `computePreview(input)` from `pnl.ts` and show computed ticks, gross P&L, and net P&L before submit. Show "—" when inputs are incomplete/invalid.
- Client-side validation mirroring backend rules (tick_size > 0, contracts ≥ 1, prices ≥ 0, exit ≥ entry) with inline messages; disable submit while invalid.
- Submit → `createTrade` (add mode) or `updateTrade` (edit mode). Surface API 400 `fields` errors inline.
- When editing, the form is pre-filled from the selected row; a "Cancel edit" action returns to add mode.

**`TradeTable.tsx`**:
- Columns: Symbol, Side, Contracts, Entry, Exit, Tick Size, Tick Value, Ticks, Gross P&L, Net P&L, Entry/Exit time, Strategy, actions (Edit, Delete).
- Edit → loads the row into `TradeForm`; Delete → confirm then `deleteTrade`.
- Empty state: "No trades yet — add your first trade above."

**`pnl.ts`** (pure, framework-free, unit-tested): `computeTicks`, `computeGrossPnl`, `computeNetPnl`, and `computePreview(input) -> { ticks, grossPnl, netPnl } | null`. Uses the same formula as the backend. Guards divide-by-zero (tick_size ≤ 0 → null).

**`api.ts`**: typed `fetch` wrappers with JSON headers; throw on non-2xx and expose the parsed `{ message, fields }` for form error display.

## Implementation Plan

### Phase 1: Foundation — remove Space Invaders, scaffold data + backend
Remove all game files, repurpose the homepage route, add the `Trade` model + migration, schemas, and controller with the P&L function.

### Phase 2: Core Implementation — API + frontend island
Implement the JSON CRUD + stats endpoints, then build the `journal` island (stats header, form with live preview, editable table) and wire it into `main.ts` and the new template.

### Phase 3: Integration — tests + validation
Add backend/Vitest/E2E tests, run all validation scripts, and confirm zero regressions.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### Step 1: Remove Space Invaders backend + homepage wiring
- Delete `src/app/views/game.py`.
- Delete `src/app/templates/game.html`.
- Delete `tests/test_game_view.py` (preserve its `TestErrorHandlers` cases — move them into the new `tests/test_journal_view.py` in Step 12, or into a `tests/test_errors.py`).
- In `src/app/views/__init__.py`, remove the `game_bp` import/registration (will be replaced with `journal_bp` in Step 6).

### Step 2: Remove Space Invaders frontend + tests
- Delete the entire `frontend/src/game/` directory (9 files).
- Delete the entire `frontend/src/islands/game/` directory (`index.tsx`, `GameIsland.tsx`).
- Delete the entire `frontend/tests/game/` directory (`SpaceInvaders.test.ts`, `entities.test.ts`).
- Delete `e2e/game.spec.ts`.
- In `frontend/src/main.ts`, remove the `game` entry from `islandRegistry` (replaced in Step 9).

### Step 3: Create the `Trade` model
- Create `src/app/models/trade.py` with the `Trade` model per the Data Model table (Numeric/Decimal fields, server-set `created_at`/`updated_at`, derived columns `ticks`/`gross_pnl`/`net_pnl`).
- Export `Trade` from `src/app/models/__init__.py` (`from .trade import Trade`; add to `__all__`).

### Step 4: Create the Alembic migration for `trades`
- Add `migrations/versions/<rev>_create_trades_table.py` with `down_revision = 'f1a2b3c4d5e6'`, `upgrade()` creating the `trades` table, `downgrade()` dropping it. Match the existing hello-migration style and this spec's column definitions.

### Step 5: Create Pydantic schemas
- Create `src/app/schemas/trade.py`: `TradeCreate`, `TradeUpdate`, `TradeResponse`, `StatsResponse`, with field validators enforcing all validation rules (tick_size > 0, tick_value > 0, contracts ≥ 1, prices ≥ 0, fees ≥ 0, side ∈ {long, short}, exit_at ≥ entry_at, exit fields required). Reject/ignore client-supplied derived fields.
- Export from `src/app/schemas/__init__.py`.

### Step 6: Create the controller (P&L + CRUD + stats)
- Create `src/app/controllers/trade.py` with plain functions (no decorators): `compute_pnl(...)` (Decimal math, single source of truth), `create_trade`, `update_trade`, `delete_trade`, `get_trade`, `list_trades`, `compute_stats`. `create_trade`/`update_trade` always recompute and persist `ticks`/`gross_pnl`/`net_pnl`.
- Export from `src/app/controllers/__init__.py`.

### Step 7: Create the `journal_bp` view (page + JSON API)
- Create `src/app/views/journal.py` defining `journal_bp`:
  - `GET /` → `render_template('journal.html')`.
  - `GET /api/trades`, `POST /api/trades`, `GET/PUT/DELETE /api/trades/<int:trade_id>`, `GET /api/trades/stats` — thin routes that validate with schemas, call the controller, and return JSON (status codes per the API section).
- Routes catch validation errors and return 400 JSON with a `fields` map; missing rows return 404 JSON.
- Register `journal_bp` in `src/app/views/__init__.py`.

### Step 8: Create the homepage template
- Create `src/app/templates/journal.html` extending `base.html`: title "Trading Journal", `<h1>`, and `<div data-island="journal">` with a `<noscript>` fallback (mirror the old `game.html` structure/Tailwind usage).

### Step 9: Create the frontend `journal` island scaffolding + registry
- Create `frontend/src/journal/types.ts`, `frontend/src/journal/pnl.ts`, `frontend/src/journal/api.ts`.
- Create `frontend/src/islands/journal/index.tsx` (`mount`) and `frontend/src/islands/journal/JournalIsland.tsx`.
- In `frontend/src/main.ts`, add `journal: () => import('./islands/journal')` to `islandRegistry`.

### Step 10: Build the UI components
- Create `frontend/src/islands/journal/StatsHeader.tsx`, `TradeForm.tsx` (with live `computePreview` P&L preview + client validation), and `TradeTable.tsx` (edit/delete). Wire them together in `JournalIsland.tsx` with fetch-on-mount and refetch-after-mutation.

### Step 11: Create the E2E test file
- Create `e2e/journal.spec.ts` (Playwright): load `/`; assert title "Trading Journal" and the `[data-island="journal"]` mount; fill the add-trade form with a known ES long trade (entry 5000 → exit 5010, tick 0.25, tick_value 12.5, 2 contracts, fees 4.5); assert the live preview shows the expected ticks/net P&L; submit; assert a new table row appears with `Net P&L = 995.50` (or `995.5`) and that the Stats header updates (# Trades increments, Total Net P&L reflects the trade). Capture a screenshot of the populated journal. Use `--reporter=list` conventions from `AGENTS.md`.

### Step 12: Create backend + frontend unit tests
- `tests/test_pnl.py` — P&L math edge cases (see Testing Strategy).
- `tests/test_trade_model.py` — persistence + derived-column correctness + `net_pnl == gross_pnl - fees`.
- `tests/test_journal_view.py` — page route (200, title, `data-island="journal"`), full CRUD via the JSON API, stats endpoint (including empty-journal zeros), validation 400s, and 404s; move over the `TestErrorHandlers` cases from the deleted game test.
- `frontend/tests/journal/pnl.test.ts` — Vitest for `pnl.ts` (long/short, fractional ticks, tick_size ≤ 0 → null, multi-contract).
- `frontend/tests/journal/form.test.ts` — Vitest for form validation helpers (rejects tick_size ≤ 0, contracts < 1, exit < entry, missing exit).

### Step 13: Update the DB seed script (housekeeping)
- Update `script/db-seed` to stop importing the removed `Hello` model; optionally seed 2–3 sample trades using the controller so `db-seed` runs cleanly. (Non-blocking but required for a clean repo.)

### Step 14: Run Validation Commands
- Run `script/test`, `script/typecheck`, `script/lint`, and `script/test-e2e` and fix any failures until all pass with zero regressions (see Validation Commands).

## Testing Strategy

### Unit Tests
- **Backend `tests/test_pnl.py`** — `compute_pnl` correctness across sides, contracts, fees, and precision (Decimal).
- **Backend `tests/test_trade_model.py`** — create/read a `Trade`; assert stored `ticks`, `gross_pnl`, `net_pnl` match the formula and that `net_pnl == gross_pnl - fees`; assert `Numeric` round-trips.
- **Backend `tests/test_journal_view.py`** — `GET /` shell; full CRUD (`POST` 201, `GET` list/one, `PUT` recomputes, `DELETE` 204→404); `GET /api/trades/stats` on empty and populated journals; validation 400s with `fields`; 404 for missing ids; retained error-handler tests.
- **Frontend `frontend/tests/journal/pnl.test.ts`** — `pnl.ts` matches backend results for representative cases.
- **Frontend `frontend/tests/journal/form.test.ts`** — validation logic rejects invalid inputs and accepts valid ones.

### Edge Cases (must be covered)
- **Short trade**: side `short`, exit < entry → positive `ticks`/`net_pnl`; exit > entry → negative. (e.g. NQ short 18000 → 17990, tick 0.25, tick_value 5, 1 contract → ticks +40, gross +200.)
- **Zero tick size rejected**: `tick_size = 0` → API 400; `pnl.ts` returns null.
- **Negative tick size rejected**: `tick_size < 0` → API 400.
- **Fractional ticks**: prices that yield a non-integer `ticks_moved` (e.g. CL tick 0.01 with a 0.005-off price, or a non-aligned entry) → `ticks` stored with fractional precision, P&L consistent.
- **Large contract counts**: e.g. 1000 contracts → no overflow; `Numeric` precision holds; totals sum correctly.
- **Missing exit price**: `exit_price` omitted/null → API 400 (Phase 1 rejects open trades).
- **Contracts < 1**: `contracts = 0` or negative → 400.
- **Negative prices**: `entry_price`/`exit_price` < 0 → 400.
- **exit_at before entry_at** → 400.
- **Fees > gross**: `net_pnl` correctly negative even on a winning gross.
- **Scratch trade**: `net_pnl == 0` → counted as neither win nor loss; `win_rate` denominator is total trades.
- **Empty-journal stats**: 0 trades → all zeros, no divide-by-zero.

### E2E (`e2e/journal.spec.ts`)
Add a trade through the UI, assert the live preview computed P&L, submit, and assert the new table row's Net P&L and the updated Stats header (see Step 11).

## Acceptance Criteria

1. Visiting `/` renders the Trading Journal page (title "Trading Journal", `[data-island="journal"]` mount) — no Space Invaders anywhere.
2. A user can add a completed futures trade via the form; on submit it persists and appears in the trades table.
3. For a long ES trade (entry 5000, exit 5010, tick_size 0.25, tick_value 12.5, 2 contracts, fees 4.5): the row shows `ticks = 40`, `gross_pnl = 1000.00`, `net_pnl = 995.50`.
4. For the equivalent short trade (entry 5010, exit 5000, same instrument), `ticks = 40`, `gross_pnl = 1000.00`, `net_pnl = 995.50`; reversing entry/exit flips the sign.
5. The form shows a **live P&L preview** (ticks, gross, net) that updates as inputs change, before submitting.
6. A user can edit an existing trade (values recompute) and delete a trade (row disappears).
7. The stats header shows total net P&L, win rate, number of trades, average win, average loss, and total ticks, all derived from stored trades and updating after add/edit/delete.
8. The API rejects invalid input with HTTP 400 and a `fields` error map: `tick_size ≤ 0`, `contracts < 1`, negative prices, missing exit price, `exit_at < entry_at`.
9. `GET /api/trades/stats` on an empty journal returns all-zero stats with no error.
10. All P&L math uses tick-based Decimal computation (never a raw price-difference dollar amount), consistent between backend and the frontend preview.
11. `script/test`, `script/typecheck`, `script/lint`, and `script/test-e2e` all pass with zero errors and zero regressions.

## Validation Commands

Execute every command to validate the feature works correctly with zero regressions.

```bash
# Install dependencies (first time)
script/bootstrap

# Create .env, database, and run migrations (incl. the new create_trades_table)
script/setup

# Backend + frontend unit tests (pytest + vitest)
script/test

# TypeScript + Python type checking (mypy + tsc)
script/typecheck

# Linting (flake8 + eslint)
script/lint

# End-to-end tests (Playwright; auto-starts dev servers)
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
- No decorators for business logic (`controllers/trade.py` is plain functions); Flask route decorators on the blueprint are fine.
- Single-user, no authentication — all trades are global, matching the prior Space Invaders / Hello World features.
- Follows the existing app-factory / blueprint / models-base / Islands (`data-island` + `main.ts` registry) patterns; reuses the content-negotiated error handlers for JSON API errors.

### Assumptions
- Phase 1 records **completed (closed)** trades only; exit fields are required.
- `tick_value` is the dollar value of one tick for one contract; the contract multiplier is applied to dollars, not to `ticks` (per-trade `ticks` is per-contract movement).
- Datetimes are handled/stored in UTC; the UI may present local time but sends ISO-8601.
- SQLite (test config) adequately exercises `Numeric` for tests; PostgreSQL is the runtime DB.

### Phase 2 (future work — NOT planned here)
- **Automated trade import/sync**: connect to broker/exchange APIs (e.g. Tradovate, Interactive Brokers, Rithmic) or import CSV/statement files to create trades automatically instead of manual entry.
- **Instruments table**: `symbol → tick_size, tick_value, exchange, multiplier` so tick specs auto-fill (and can be auto-fetched) rather than typed per trade; `trades` retains per-trade snapshot columns for historical accuracy.
- **Open/running positions**: nullable exit + a `status` column and unrealized P&L.
- **Multi-user / authentication**: scope trades to an account/user.
- **Charting & analytics**: equity curve, P&L-by-instrument, distribution charts (only summary numbers are in scope for Phase 1).

The Phase 1 design leaves room for all of the above: per-trade snapshot columns survive an instruments table; the controller's single `compute_pnl` stays the source of truth for both manual and imported trades; the JSON API can gain an import endpoint without changing the read/stats surface.
```
