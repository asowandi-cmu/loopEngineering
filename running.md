# Running the App

This is the **trading journal** application — a Flask + React Islands app backed by PostgreSQL. This guide covers running it a codespace.

## Tech Stack

- **Backend**: Flask 3, SQLAlchemy 2, Python 3.12
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Database**: PostgreSQL 16

## Prerequisites

- Python 3.12
- Node 20
- PostgreSQL 16 (running locally)
- Open this repository in a codespace and inside local visual studio code (not from browser) [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/asowandi-cmu/loopEngineering)

> In **GitHub Codespaces** these are pre-installed and `script/setup` runs automatically on container create — you can skip straight to [Start the servers](#3-start-the-servers).

## 1. Setup (first time)

Bootstraps everything: installs dependencies, creates `.env` from `.env.example`, creates the database, runs migrations, and installs pre-commit hooks.

```bash
./script/setup
```

## 2. Configure environment (optional)

`script/setup` copies `.env.example` to `.env` automatically. Edit `.env` if your database or ports differ from the defaults:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
FLASK_ENV=development
FLASK_SECRET_KEY=change-me-in-production
FLASK_DEBUG=1
VITE_DEV_SERVER=http://localhost:5174
```

## 3. Start the servers

Runs the Flask backend and Vite dev server concurrently:

```bash
./script/server
```

This starts two servers:

- **Flask** (port **5000**) — serves the app's HTML pages. **This is the one you open.**
- **Vite** (port **5174**) — serves JS/CSS assets only. Not meant to be opened directly.

> ⚠️ **Open http://localhost:5000 — not 5174.**
> This is a React Islands app: Flask renders the HTML, and that HTML loads the React bundle from Vite behind the scenes. Visiting **http://localhost:5174** directly returns a **404** (its root has no page) and shows a blank screen. Always point your browser at **port 5000**.

Stop both servers with `Ctrl+C`.

### GitHub Codespaces

Both ports must be **forwarded** for the app to work:

- **5000** — the URL you open in your browser.
- **5174** — must also be forwarded, because the HTML loads assets from `http://localhost:5174`. If it isn't reachable, the page loads but the interactive React island stays blank.

Check the VS Code **Ports** tab and confirm both **5000** and **5174** are forwarded, then open the forwarded **5000** URL.

## Other Commands

```bash
./script/test        # Run pytest + vitest
./script/test-e2e    # Run Playwright browser tests (auto-starts servers)
./script/typecheck   # Run mypy + tsc
./script/lint        # Run flake8 + eslint
./script/db-seed     # Seed the database with sample data
./script/console     # Open an interactive app console
```

## Production

A `Procfile` is provided for platforms like Heroku, Railway, or Render:

```
web: gunicorn "src.app:create_app()" --bind 0.0.0.0:$PORT
```

## Troubleshooting

- **Database errors** — ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct. Re-run migrations with `FLASK_APP=src/app:create_app flask db upgrade`.
- **Blank page / "nothing loads"** — you're probably opening **port 5174**. Open **http://localhost:5000** instead. Port 5174 only serves assets and returns a 404 at its root.
- **Frontend assets not loading** — make sure the Vite dev server (port 5174) is running (`script/server` starts it alongside Flask) and, in Codespaces, that port 5174 is forwarded.
- **Port already in use** — stop the process on ports 5000 / 5174, or adjust the ports/`VITE_DEV_SERVER` accordingly.
