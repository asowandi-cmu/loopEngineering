## Build & Run

**Bootstrap** (first time only):
```bash
script/bootstrap  # Installs Python and Node dependencies
```

**Setup** (first time and after migrations):
```bash
script/setup  # Creates .env, database, runs migrations
```

**Server** (development):
```bash
script/server  # Starts Flask on :5000 + Vite on :5174
```

## Cleanup

Run these slash commands to clean up code:
- `/python-code-simplifier` - Simplifies recently modified Python code for clarity and maintainability while preserving functionality.
- `/typescript-code-simplifier` - Simplifies recently modified TypeScript code for clarity and maintainability while preserving functionality.

## Validation

IMPORTANT ALWAYS RUN these after implementing to get immediate feedback:

- Tests: `script/test` → `pytest` + `vitest`
  - Direct: `PYTHONPATH=src pytest tests/` (backend) + `cd frontend && npm test` (frontend)
- E2E: `script/test-e2e` → Playwright browser tests
  - Direct: `npx playwright test --reporter=list` (auto-starts dev servers; use `--reporter=list` in non-interactive shells — the default `html` reporter opens a blocking report server that hangs CI/agents)
  - First run needs browsers: `npx playwright install chromium`
  - UI mode: `script/test-e2e --ui`
- Typecheck: `script/typecheck` → `mypy` + `tsc`
  - Direct: `mypy src/ --ignore-missing-imports` + `cd frontend && npm run typecheck`
- Lint: `script/lint` → `flake8` + `eslint`
  - Direct: `flake8 src/ tests/` + `cd frontend && npm run lint`

## Operational Notes

- **Backend**: Flask on :5000, `PYTHONPATH=src` required when running pytest directly
- **Frontend**: Vite dev server on :5174, React Islands pattern with `data-island` attributes in templates
- **Database**: PostgreSQL, connection via `DATABASE_URL` env var (set by `script/setup`)
- **Dev environment**: `.env` created by `script/setup`, contains all runtime config

### Codebase Patterns

- Backend: Python/Flask in `src/`, tests in `tests/`
- Frontend: React in `frontend/`, compiled to static assets
- Templates: Jinja2 with Islands hydration points (`data-island` attributes)
- Migrations: Alembic in `migrations/`, auto-applied by `script/setup`
- E2E tests: Playwright in `e2e/`, config in `playwright.config.ts`

### Browser Testing

A **Playwright MCP server** is configured in `.vscode/mcp.json` for interactive browser testing via agent mode. Use the `/test-in-browser` slash command for the full workflow — it teaches you how to navigate the app, interact with elements, and verify results using accessibility snapshots.


### Commit Messages
Use the slash command `/git-commit` to create well-structured git commits.
