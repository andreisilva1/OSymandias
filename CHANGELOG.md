# Changelog

All notable changes to OSymandias are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for 1.2

- **Lite mode** (`osy serve --lite`) — zero-Docker first-contact run. Swaps the server
  stack for embedded equivalents (SQLite, local Qdrant, in-process async execution),
  storing data under `.osy/` in the working directory. Sub-tasks still run
  concurrently. Built for dev and demo, not production.

## [1.1.1] - 2026-06-21

### Added

- **Token budget caps** — set `max_tokens` on a job; the runtime halts with
  `BUDGET_EXCEEDED` before a runaway loop drains the quota.
- **Human-in-the-loop approval** — mark an agent (`requires_approval`) or an
  individual task to gate it; work waits in `HUMAN_REVIEW` until approved
  (enforced server-side). A cross-job **Approvals** inbox lists everything pending.
- **Lifecycle webhooks** — register a URL and receive a POST on `JOB_COMPLETED`,
  `JOB_FAILED`, or `BUDGET_EXCEEDED`.
- **Real cost & token tracking** — per-agent and per-tool breakdown, priced via LiteLLM.
- **Execution traces** — the full reasoning chain (events, tool calls, conversation)
  for any task.
- **Deterministic LLM response cache** — opt-in (`LLM_CACHE_ENABLED`); identical calls
  return from cache, cutting cost and latency on retries and replays.
- **CLI** — `osy submit` to submit a goal and stream it live with `--watch`;
  `osy init --example` scaffolds a runnable tool + agent.
- **Dashboard** — budget field, approve button, COST and TRACE tabs, failure-reason
  banner, lifecycle toasts, onboarding empty state, and a webhooks page.
- **Official Portuguese documentation** (`DOCS_pt-br.md`).

### Fixed

- Eliminated N+1 queries in the agent context loop.
- Closed a Redis connection leak under load.
- Removed circular imports between workers (dispatch via Celery `send_task`).
- Guarded against a planner returning an empty plan, which previously left a job
  stuck indefinitely.

### Changed

- Pydantic-based response serialization across the API.

---

Releases before 1.1.1 (`v1.0.1`, `v1.0.0`, `v0.2.1`, `v0.1.6`) predate this changelog;
see the [git tags](https://github.com/andreisilva1/OSymandias/tags) for that history.
