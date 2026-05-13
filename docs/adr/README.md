# Architecture Decision Records

## ADR-001: FastAPI + Vue 3 SPA over Next.js or Remix

**Date:** 2026-05  
**Status:** Accepted  

**Context:** We needed a frontend/backend split for the LLM inference gateway. Candidates: monorepo SPA (FastAPI+Vue), full-stack framework (Next.js, Remix), or pure API (no dashboard).

**Decision:** Use FastAPI for backend (Python native, async, OpenAPI auto-docs) and Vue 3 Composition API + Pinia for frontend. Vue SPA is served as static files from the FastAPI app.

**Consequences:**
- Single binary deployment (no separate frontend server)
- JWT auth via httpOnly cookies (browser auto-sends)
- WebSocket real-time metrics via `/ws/metrics`
- Frontend built to `frontend/dist/` and served by FastAPI

---

## ADR-002: SQLite for Dev, PostgreSQL for Prod

**Date:** 2026-05  
**Status:** Accepted  

**Context:** Need zero-config for development, full SQL for production.

**Decision:** Auto-detect PostgreSQL availability. Fall back to SQLite with `Base.metadata.create_all()` in dev. Use Alembic migrations + PostgreSQL for production.

**Consequences:**
- New developers start with zero setup
- Production enforces PostgreSQL via `validate_production_settings()`
- Alembic autogenerate works across both databases

---

## ADR-003: Pluggable Guardrails Pipeline

**Date:** 2026-05  
**Status:** Accepted  

**Context:** Content safety needs vary by deployment. Some teams want strict blocking, others only need PII redaction.

**Decision:** Pluggable guardrail pipeline with per-stage actions (block/flag/sanitize/allow). Three built-in guardrails: Prompt Injection Detection, PII Redaction, Content Safety. Configurable via `ecoguard.yaml` or `GUARDRAILS_ENABLED=true`.

**Consequences:**
- Each guardrail is independent and async
- Pipeline stops on first BLOCK action
- Custom guardrails addable via plugin system

---

## ADR-004: HTTP-Only JWT Cookies over Bearer Tokens

**Date:** 2026-05  
**Status:** Accepted  

**Context:** XSS can exfiltrate JWTs from localStorage. httpOnly cookies prevent JavaScript access.

**Decision:** Backend sets `eco_guard_token` as httpOnly, secure (in prod), sameSite=strict cookie. Frontend uses `credentials: 'include'` for all API calls. Backend also supports `Authorization: Bearer` headers for CLI/SDK access.

**Consequences:**
- Browser auth is transparent (no token management in JS)
- SDK/CLI still works via Bearer tokens or API keys
- CSP headers provide second line of XSS defense

---

## ADR-005: Background Tasks as asyncio.create_task

**Date:** 2026-05  
**Status:** Accepted  

**Context:** Need background loops for metrics broadcast, GPU monitoring, cron scheduler, async inference worker, provider auto-recovery, and GitOps config watcher.

**Decision:** Use `asyncio.create_task()` within the FastAPI lifespan. Each task runs in the same event loop. Tasks are stored in a `_tasks` list and cancelled on shutdown with graceful drain.

**Consequences:**
- No external task queue needed
- Not suitable for >1 worker (tasks duplicate)
- For multi-worker deployments, use Redis-backed cron/scheduling
