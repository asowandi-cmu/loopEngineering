# Running the App

This is the **trading journal** application — a Flask + React Islands app backed by PostgreSQL. This guide covers running it locally (or in a Codespace).

## Tech Stack

- **Backend**: Flask 3, SQLAlchemy 2, Python 3.12
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Database**: PostgreSQL 16

## Prerequisites

- Python 3.12
- Node 20
- PostgreSQL 16 (running locally)

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
VITE_DEV_SERVER=http://localhost:5173
```

## 3. Start the servers

Runs the Flask backend and Vite dev server concurrently:

```bash
./script/server
```

- **Flask** (backend): http://localhost:5000
- **Vite** (frontend assets): http://localhost:5173

Open **http://localhost:5000** in your browser. Flask serves the HTML and loads assets from Vite. Stop both servers with `Ctrl+C`.

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
- **Frontend assets not loading** — make sure the Vite dev server (port 5173) is running; `script/server` starts it alongside Flask.
- **Port already in use** — stop the process on ports 5000 / 5173, or adjust the ports/`VITE_DEV_SERVER` accordingly.
