# ADR-0008: Split Deploy Workbench From Lab Benchmark

- Date: 2026-07-19
- Status: Accepted

## Context

Minsight V3 made the Lab console useful for both product demos and benchmark
iteration. That is convenient locally, but it is the wrong production boundary:

- Benchmark APIs expose regression runs, historical run archives, judge output,
  and test fixtures.
- The deployable product should only expose meeting workbench behavior.
- V4 needs a clear path toward Docker, production environment variables,
  persistent jobs, and Postgres without publishing Lab-only surfaces.

## Decision

Add a separate `Deploy/` project as the production-facing boundary.

`Deploy/` includes:

- `Deploy/server.py`
  Workbench-only HTTP API and static frontend serving.
- `Deploy/runtime.py`
  Production-facing meeting lifecycle: create meeting, run Minsight Agent,
  persist minutes/actions/decisions/tasks, and call Feishu sync sinks.
- `Deploy/web/`
  Workbench-only list/detail frontend.
- `Deploy/tests/`
  Public seam tests for deploy HTTP behavior and runtime contracts.
- `Deploy/store.py`
  Workbench-only SQLite persistence, with no benchmark tables.
- `Deploy/integrations/`
  Production-facing Feishu sync adapters.

`Deploy/` intentionally does not expose:

- `/api/run`
- `/api/runs`
- `/api/scenarios`
- benchmark run creation
- LLM judge scoring
- objective metrics
- V1 archive UI
- regression heatmaps

`Lab/` remains the offline benchmark and experimentation project.

## Runtime Contract

`GET /api/demo/meeting?id=<meeting_id>` returns frontend-facing workbench
fields:

- `meeting.title`, `meeting.status`, `meeting.error_message`,
  `meeting.scenario`, `meeting.created_at`
- `minutes.title`, `minutes.summary_line`, `minutes.participants[]`,
  `minutes.key_points[]`
- `derived_tasks[].sync_status`, `derived_tasks[].external_url`,
  `derived_tasks[].sync_error`
- `decisions[].base_sync_status`, `decisions[].base_url`
- `alerts[].title`, `alerts[].message`, `alerts[].type`

`base_url` is a deploy-facing alias for the stored Feishu Base record URL
(`base_external_url`). This keeps the frontend contract stable without forcing a
database rename.

## Interrupted Job Guard

Deploy currently uses in-memory background threads for meeting extraction. If
the server process restarts, a thread can disappear while SQLite still says the
meeting is `queued` or `running`.

To avoid permanent "running" UI states, `Deploy/runtime.py` exposes
`recover_interrupted_meetings()`, and `Deploy/server.py` calls it on startup.
It marks stale `queued`/`running` meetings as:

```text
status = failed
phase = interrupted
```

This is a V4 demo hardening guard, not the final production job architecture.

## Deployment Skeleton

Deploy now includes a minimal container packaging path:

- `Deploy/Dockerfile`
  Builds the workbench-only service and starts `Deploy/server.py`.
- `Deploy/requirements.txt`
  Captures the deploy runtime Python dependencies without installing Lab test
  tooling.
- `Deploy/.env.production.example`
  Documents production environment variables and defaults Feishu sync to
  `dry_run`.
- `Deploy/scripts/smoke_check.py`
  Verifies `/health`, demo case listing, and that benchmark-only routes remain
  hidden.
- `Deploy/scripts/validate_env.py`
  Fails fast when production env vars are missing, placeholder-like, or not in
  production mode.
- `Deploy/ops/`
  Contains systemd and Nginx templates for Aliyun ECS / Lightweight Application
  Server deployment.
- `.dockerignore`
  Keeps local `.env`, SQLite databases, benchmark results, cache files, and
  ignored docs out of the image build context.

This is intentionally a smoke-deploy skeleton, not final infrastructure. It
keeps SQLite mounted at `/data` for the V4 prototype while preserving the path
to later Postgres and durable worker hardening.

## Consequences

- The deployable surface is smaller and safer.
- Lab benchmark functionality can continue evolving without being published.
- Frontend list/detail workbench can depend on explicit field contracts.
- Stale in-memory jobs no longer leave the UI stuck in "running" forever.
- Docker builds now have a clear production entrypoint and a smoke check for
  route isolation.
- Deploy no longer imports `Lab/store.py` or copies `Lab/` into the Docker
  image.
- Production mode no longer loads local `.env` files from Core, the repository
  root, or Lab.

## Follow-Ups

- Replace in-memory threads with a durable job queue or worker model.
- Add Postgres store implementation and migrations.
- Add HTTPS/TLS termination instructions after the deployment domain is chosen.

## Validation

Covered by:

- `Deploy/tests/test_server.py`
- `Deploy/tests/test_runtime.py`
- `Lab/tests/*`

Run:

```powershell
python -m unittest discover -s D:\Interview\Minsight\Deploy\tests -v
python -m unittest discover -s D:\Interview\Minsight\Lab\tests -v
node --check D:\Interview\Minsight\Deploy\web\app.js
node --check D:\Interview\Minsight\Lab\web\app.js
```
