# PRODUCTION RUNBOOK — Universal Agentic AI

## Go-live (public) checklist
1. **Host**: any Docker host / VPS / Railway / Render. `docker compose up -d --build`.
2. **Secrets**: set `OPENAI_API_KEY` (or an OpenAI-compatible `OPENAI_BASE_URL`) for LLM
   planning/drafting — without it the platform runs on the local template planner.
   Never commit keys; inject via the host's secret store.
3. **Auth**: set `UAA_REQUIRE_AUTH=1`, register the Founder account FIRST (first
   account becomes FOUNDER), then open registrations.
4. **Domain + HTTPS**: put the host's reverse proxy / platform TLS in front of :8100.
5. **Backups**: snapshot the `uaa-data` volume (events, incidents, tasks, auth,
   factory, business databases + generated outputs).
6. **Client apps**: web works everywhere today. Android/iOS/Windows/macOS shells
   wrap this same web app + API (shared-codebase decision, Doc 29) — they need
   the Founder's Play Console ($25) / Apple Developer ($99/yr) accounts to publish.

## Operate
- Health: `GET /api/health` · Watchdog: `GET /api/watchdog` · Monitor: `GET /api/monitor`
- Incidents: Server Room → Incidents tab; open CRITICAL/HIGH need Founder review.
- Level-3 changes (schema, auth, core logic, safety): use the Approvals queue —
  nothing in the system applies them automatically.
- Rollback: redeploy the previous image; databases are additive SQLite stores —
  restore the `uaa-data` snapshot taken before the deploy.

## Known production gaps (honest list)
- SQLite stores are single-node; move to PostgreSQL before multi-instance scaling (Doc 10/22).
- Generative image/video/audio models are not yet connected — media tasks produce
  plans and FFmpeg scene-card preview renders, clearly labelled as such.
- No payment/billing yet (Doc 20); no email/SMS notifications yet.
