# Implementation Plan — Space Invaders Classic Gameplay

## Status

> **Overall: 100% Complete — Feature implemented, all validation green.**

Spec: `specs/space-invaders-classic-gameplay.md` (comprehensive, self-contained).

The Hello World scaffold has been fully removed and replaced with a client-side
Space Invaders game mounted via the React Islands architecture. All unit tests
(pytest + vitest), type checks (mypy + tsc), linters (flake8 + eslint), and
Playwright E2E tests pass.

---

## What was built (2026-05-29)

### Backend
- `src/app/views/game.py` — `game_bp`; `GET /` renders `game.html` (no DB, no API).
- `src/app/templates/game.html` — extends `base.html`; title "Space Invaders" + `data-island="game"` mount + `<noscript>` fallback.
- Registered `game_bp` in `src/app/views/__init__.py`.
- `migrations/versions/f1a2b3c4d5e6_drop_hello_table.py` — drops `hello` (down recreates it), chained after the original create migration so `script/setup` stays reproducible.
- Removed: `views/hello.py`, `controllers/hello.py`, `models/hello.py`, `schemas/hello.py`, `templates/hello/`, and cleared their `__init__` exports.
- `tests/test_game_view.py` — `GET /` 200, contains `data-island="game"`, title is "Space Invaders". Retained `TestErrorHandlers` (404 HTML/JSON) so error-handler coverage survives.

### Frontend engine (`frontend/src/game/`, framework-agnostic, dt-based)
- `types.ts`, `constants.ts` (px/s speeds; 5×11 grid; per-row points; colors).
- `Bullet.ts` (sign of speed = direction; off-screen → dead).
- `Player.ts` (bounds-clamped movement; shot cooldown rate-limits held Space).
- `Alien.ts` (thin data class) + `AlienGrid.ts` (lock-step march, edge reverse+descend, speed-up as swarm thins, bottom-of-column firing, `reachedBottom`, `isCleared`).
- `InputHandler.ts` (held-key set + edge-triggered `consumeStart()`; `destroy()` removes listeners).
- `Renderer.ts` (geometric shapes only; start/gameover/win screens; HUD score).
- `SpaceInvaders.ts` (RAF loop, frame-rate-independent dt clamped to 0.05s, AABB collisions, state machine start→playing→won/gameover→restart, `start()`/`reset()`/`destroy()`).

### Island integration
- `frontend/src/islands/game/GameIsland.tsx` — thin React wrapper; creates engine + `start()` on mount, `destroy()` on unmount.
- `frontend/src/islands/game/index.tsx` — `mount()` clears fallback and renders.
- `frontend/src/main.ts` registry maps `game: () => import('./islands/game')`.
- `frontend/src/types/index.ts` — Hello types removed, generic `IslandProps` kept.
- Removed Hello frontend + `frontend/tests/islands/hello/`.

### Tests
- `frontend/tests/game/entities.test.ts` (11) — boundary clamp, bullet pruning, swarm reversal/descent, column-front firing, clear/reachedBottom.
- `frontend/tests/game/SpaceInvaders.test.ts` (7) — state transitions, win/lose, restart, missing-context throw, destroy cleanup (stub canvas context).
- `e2e/game.spec.ts` (4) — title, canvas 800×600 visible, no console errors on input, canvas changes on Space.

---

## Validation results (all green)
- `PYTHONPATH=src pytest tests/` → 5 passed.
- `cd frontend && npm test` → 18 passed.
- `mypy src/` → clean (10 files). `flake8 src/ tests/` → clean.
- `cd frontend && npm run typecheck` (tsc) → clean. `npm run lint` (eslint) → clean.
- `npx playwright test --reporter=list` → 4 passed.
- `cd frontend && npm run build` → production bundle builds clean.

---

## Notes / learnings
- Run E2E with `--reporter=list` in agent/CI shells; the default `html` reporter opens a blocking report server (this caused an initial hang). Recorded in AGENTS.md.
- Playwright browsers must be installed once: `npx playwright install chromium`.
- `vite build` empties `src/app/static/` (emptyOutDir) and removes `.gitkeep`; restore it after a local build. Built assets under `src/app/static/assets|.vite` are gitignored.
- ESLint flat config has no DOM type globals, so avoid `as EventListener` casts in engine code — type handlers as `(e: Event)` and narrow internally.
- tsc `noUnusedLocals`/`noUnusedParameters` is on: don't store constructor params you don't reference; underscore-prefix intentionally-unused params (`_props`).

## Out of scope (per spec)
Persistent high scores / new model+API, multiple levels, power-ups, sound,
mobile touch controls, sprite assets.
