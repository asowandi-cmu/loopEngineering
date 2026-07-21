# Ralph Wiggum Tutorial

A hands-on workshop for building software with AI agents using the **Ralph Wiggum loop** — an iterative, autonomous development pattern pioneered by [Geoffrey Huntley](https://ghuntley.com/loop/).

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/gwincr11/ralph-wiggum-tutorial)

## What is Ralph Wiggum Mode?

Ralph Wiggum mode is an AI development pattern where you run a coding agent in a persistent loop. Instead of hand-holding an AI step-by-step, you give it a goal, a spec, and let it iterate — fixing its own mistakes, running tests, and committing code — until the job is done.

Named after the endlessly persistent Simpsons character, the core idea is simple: software is clay on a pottery wheel. If something isn't right, throw it back on the wheel.

> *"Ralph is monolithic. Ralph works autonomously in a single repository as a single process that performs one task per loop."* — [ghuntley.com/loop](https://ghuntley.com/loop/)

**Further reading:** [Reddit breakdown](https://www.reddit.com/r/ClaudeAI/comments/1qlqaub/my_ralph_wiggum_breakdown_just_got_endorsed_as/) · [ghuntley.com/loop](https://ghuntley.com/loop/)

---

## Getting Started with Codespaces

This repo is fully configured for **GitHub Codespaces** — no local setup needed.

1. Click the **"Open in GitHub Codespaces"** button above (or go to **Code → Codespaces → New codespace**)
2. Wait for the container to build (Python 3.12, Node 20, PostgreSQL 16 are pre-installed)
3. The post-create script runs `script/setup` automatically — database, dependencies, and environment are ready
4. Start the dev server:
   ```bash
   ./script/server   # Flask on :5000, Vite on :5174
   ```

---

## The Loop

The entire workflow is driven by `loop.sh` — a bash script that runs Copilot CLI in a `while true` loop with a prompt file, pushing code after each iteration.

```
┌─────────────────────────────────────────────┐
│                  loop.sh                    │
│                                             │
│  ┌─────────┐    ┌─────────┐    ┌────────┐  │
│  │  Prompt  │───▶│ Copilot │───▶│  Push  │  │
│  │  (plan/  │    │   CLI   │    │  Code  │  │
│  │  build)  │    │         │    │        │  │
│  └─────────┘    └─────────┘    └────────┘  │
│       ▲                             │       │
│       └─────────────────────────────┘       │
│              loop until DONE                │
└─────────────────────────────────────────────┘
```

### Usage

```bash
./loop.sh                        # Build mode, unlimited loops
./loop.sh -m plan                # Plan mode
./loop.sh -m plan -n 5           # Plan mode, max 5 iterations
./loop.sh -n 10 -s "DONE"       # Build mode, stop on "DONE"
./loop.sh -p custom_prompt.md    # Custom prompt file
```

The loop stops when: the agent outputs the completion promise (`DONE`), max iterations are reached, or you hit `Ctrl+C`.

---

## The Workflow: Plan → Review → Build → Correct

### 1. Plan (`PROMPT_plan.md`)

Runs the agent in analysis-only mode. It:
- Studies specs in `specs/` and the existing codebase using parallel subagents
- Compares source code against specifications
- Creates/updates `IMPLEMENTATION_PLAN.md` with a prioritized task list
- **Does NOT implement anything** — only plans

```bash
./loop.sh -m plan -n 3
```

### 2. Review the Plan (`plan-reviewer` agent)

The plan-reviewer agent (`.github/agents/plan-reviewer.md`) acts as a technical reviewer:
- Spawns subagents to validate feasibility, completeness, and alignment with project standards
- Checks that external packages are real, test plans are comprehensive, and nothing is disconnected
- Asks clarifying questions and provides detailed feedback
- Updates the plan to be implementation-ready

### 3. Build (`PROMPT_build.md`)

Runs the agent in implementation mode. It:
- Picks the highest-priority item from `IMPLEMENTATION_PLAN.md`
- Implements it fully (no stubs or placeholders)
- Runs tests after each change
- Commits and pushes working code
- Outputs `<promise>DONE</promise>` when everything is implemented

```bash
./loop.sh -m build
```

### 4. Correct

Watch the loop. When you see failures:
- The agent self-corrects in subsequent iterations
- If it can't, hit `Ctrl+C`, diagnose the issue, update specs or the implementation plan, and re-loop
- Persistent issues become engineering problems for you to solve so they never recur

---

## Key Files

| File | Purpose |
|------|---------|
| `loop.sh` | The main loop script — orchestrates iterations |
| `PROMPT_plan.md` | Prompt for planning mode — analyze, don't implement |
| `PROMPT_build.md` | Prompt for build mode — implement, test, commit |
| `IMPLEMENTATION_PLAN.md` | Living document tracking what's done and what's next |
| `AGENTS.md` | Operational reference (ports, commands, patterns) for the agent |
| `specs/` | Application specifications the agent builds against |

## GitHub Agents & Skills

### Agents (`.github/agents/`)

| Agent | Role |
|-------|------|
| **plan-agent** | Plans features by deep-exploring the codebase, then outputs structured specs to `specs/` with phases, tasks, testing strategy, and acceptance criteria |
| **plan-reviewer** | Reviews plans for completeness and feasibility — validates packages exist, test coverage is adequate, and features are properly integrated |

### Skills (`.github/skills/`)

| Skill | What it does |
|-------|-------------|
| **git-commit** | Creates commits with AI-generated messages following Conventional Commits; attaches git notes with reasoning for significant decisions |
| **test-in-browser** | Drives a headless browser via Playwright MCP to verify features end-to-end using accessibility snapshots |
| **python-code-simplifier** | Refactors Python code for clarity while preserving behavior — enforces PEP 8, type annotations, early returns |
| **typescript-code-simplifier** | Refactors TypeScript code for clarity — enforces strict typing, clean imports, small components |

---

## Development Commands

```bash
./script/setup       # Bootstrap environment + database
./script/server      # Start dev servers
./script/test        # Run pytest + vitest
./script/test-e2e    # Run Playwright browser tests
./script/typecheck   # Run mypy + tsc
./script/lint        # Run flake8 + eslint
```

## Tech Stack

- **Backend**: Flask 3, SQLAlchemy 2, Python 3.12
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Database**: PostgreSQL 16
- **Testing**: pytest, Vitest, Playwright
- **Architecture**: React Islands (server-rendered HTML + selective React hydration)

## License

Educational tutorial application.
