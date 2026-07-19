# Minsight Deploy

`Deploy/` is the production-facing boundary for Minsight.

It exists so deployable services can be built without publishing the Lab
benchmark console, LLM judge workflow, historical run archive, or regression
heatmaps.

## Scope

Included:

- Workbench HTTP APIs for meeting extraction.
- Workbench-only static frontend.
- Manual Feishu Task sync for derived action items.
- Manual Feishu Base sync for meeting decisions.
- Health endpoint for deploy/runtime checks.

Excluded:

- Benchmark APIs such as `/api/run`, `/api/runs`, and `/api/scenarios`.
- LLM judge and objective metrics execution.
- Benchmark result archive and heatmaps.
- V1 baseline archive UI.

## Frontend Field Contract

`GET /api/demo/meeting?id=<meeting_id>` returns workbench details for the
deploy frontend.

Important public fields:

- `meeting.title`, `meeting.status`, `meeting.error_message`,
  `meeting.scenario`, `meeting.created_at`
- `minutes.title`, `minutes.summary_line`, `minutes.participants[]`,
  `minutes.key_points[]`
- `derived_tasks[].title`, `derived_tasks[].assignee`,
  `derived_tasks[].due_date`, `derived_tasks[].source_evidence`,
  `derived_tasks[].sync_status`, `derived_tasks[].external_url`,
  `derived_tasks[].sync_error`
- `decisions[].decision`, `decisions[].supersedes`, `decisions[].evidence`,
  `decisions[].base_sync_status`, `decisions[].base_url`
- `alerts[].title`, `alerts[].message`, `alerts[].type`

`base_url` is the deploy-facing alias for the stored Feishu Base record link.
The lower-level storage field remains `base_external_url`.

## Run Locally

From this folder:

```powershell
python server.py
```

Then open:

```text
http://127.0.0.1:8788
```

Useful environment variables:

```env
MINSIGHT_HOST=127.0.0.1
MINSIGHT_PORT=8788
MINSIGHT_DB_PATH=./minsight_deploy.sqlite
MINSIGHT_FEISHU_SYNC_MODE=dry_run
MINSIGHT_FEISHU_BASE_SYNC_MODE=dry_run
```

For production, prefer process-level environment variables over local `.env`
files. A later V4 slice should make Feishu adapters ignore local Lab `.env`
files when running in production mode.

## Current Boundary

`Deploy/runtime.py` now owns the production-facing workbench lifecycle:

- create a meeting job
- run the formal Minsight Agent
- persist readable minutes, actions, decisions, and derived tasks
- sync tasks and decisions to Feishu sinks

It does not include benchmark run creation, LLM judge scoring, objective
metrics, V1 archives, or regression heatmaps.

To keep this refactor low-risk, `Deploy/runtime.py` still reuses the current
SQLite store and Feishu integration adapters from `Lab/`. Those modules should
be moved into a shared production package before Docker/Postgres hardening.

Next refactor target:

- Move the SQLite store out of `Lab/`.
- Move Feishu integrations into a shared production package.
- Keep `Lab/` as an offline benchmark project only.
