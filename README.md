# UNIVERSAL AGENTIC AI

One central intelligence. One management hierarchy. Hundreds of specialised AI workers.
One live AI Server Room. One always-available cloud workforce.

**Status:** Batches 1–10 built and verified (2026-10-31) — **18/18 tests passing**,
server live on port 8100. Full platform core: agent registry (325 agents, 20
departments), Main AI planner (LLM via Model Router when a key is configured,
template fallback otherwise), Management AI assignment, durable tasks, incident
system with Level-1 self-healing, independent watchdog, heartbeat monitor, auth
with Founder approvals, Agent Factory, Business OS (tenant-isolated), FFmpeg
MP4 preview renders, and a full Server Room web app. Go-live details and the
honest remaining-gaps list: see `PRODUCTION.md` and the project GO-LIVE report.

## Run it

```bash
cd ~/workspace/universal-agentic-ai
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100 --app-dir backend
# or: ./run.sh
```

Open http://localhost:8100 — the Server Room (DEV mode, clearly labelled).
Submit an objective, e.g. *"Create a 15-minute animated educational film about
Artificial Intelligence"* or *"Build a complete CRM system for a real estate company"*,
and watch real delegation events stream in the Live Command Terminal.

## API

- `GET /api/health` · `GET /api/stats`
- `GET /api/departments` · `GET /api/agents?department_id=D06` · `GET /api/agents/{id}`
- `POST /api/agents/{id}/pause|resume|disable|quarantine|enable`
- `POST /api/objectives {title, priority}` · `GET /api/objectives` · `GET /api/objectives/{id}`
- `GET /api/events?limit=100&agent=MAIN_AI`

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest tests/ -q   # 10 passed (incl. self-healing)
```

## What is real, what is not (honesty box)

REAL in Batches 1-2: the full agent registry (323 agents, 20 departments, every specialist
from Master Prompt v3.0 section 9 plus the Management AI technical-operations hierarchy),
skill-based assignment, the task lifecycle, the persistent event log (SQLite), per-task
artifact files, the quality gate, agent pause/resume/disable/quarantine controls, the
Server Room page reading live data, a full incident system (severity classification,
lifecycle, SQLite store), Level-1 self-healing (failed tasks are reassigned to another
specialist and retried once — test it by prefixing an objective title with [fail-first]),
and an independent watchdog endpoint (GET /api/watchdog).

NOT yet: LLM intelligence (the planner is rule-based v0.1 behind a replaceable
interface; the Model Router is Batch 2), rendered video/images/audio (media tasks
produce production plans, labelled as such on their face), cloud deployment,
auth/multi-tenancy, and the native client apps (web client works; Android/iOS/
Windows/macOS shells come after the API stabilises). Objectives/tasks are in-memory
in Batch 1 (events persist); durable task storage is Batch 2.
