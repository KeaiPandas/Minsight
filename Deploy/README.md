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
MINSIGHT_HOST=0.0.0.0
MINSIGHT_PORT=8788
MINSIGHT_CONFIG_MODE=production
MINSIGHT_DB_PATH=/var/lib/minsight/minsight_deploy.sqlite
MINSIGHT_FEISHU_SYNC_MODE=dry_run
MINSIGHT_FEISHU_BASE_SYNC_MODE=dry_run
```

Deploy defaults to `MINSIGHT_CONFIG_MODE=production` from
`Deploy/runtime.py`. In this mode, Core and Feishu adapters do not load local
`.env` files. The server must receive secrets from process-level environment
variables or `/etc/minsight/minsight.env`.

## Aliyun ECS / Lightweight Server

Recommended single-machine path:

```powershell
git clone <your-repo-url> /opt/minsight
cd /opt/minsight
sudo bash Deploy/scripts/bootstrap_aliyun.sh
sudo nano /etc/minsight/minsight.env
sudo systemctl enable --now minsight
sudo systemctl reload nginx
python Deploy/scripts/smoke_check.py http://127.0.0.1
```

Server layout:

- code: `/opt/minsight`
- virtualenv: `/opt/minsight/.venv`
- env file: `/etc/minsight/minsight.env`
- SQLite prototype data: `/var/lib/minsight/minsight_deploy.sqlite`
- service: `minsight.service`
- Nginx reverse proxy: port `80` -> `127.0.0.1:8788`

Before opening public traffic:

- Replace every `your-*` value in `/etc/minsight/minsight.env`.
- Keep `MINSIGHT_FEISHU_SYNC_MODE=dry_run` and
  `MINSIGHT_FEISHU_BASE_SYNC_MODE=dry_run` until Feishu permissions are
  verified on the server.
- Open only port `80` at first. Add HTTPS after DNS is ready.

## Deploy-Only Git Repository

If you want a separate repository for server deployment, export a clean
deploy-only repo from the main development repository:

```powershell
powershell -ExecutionPolicy Bypass -File Deploy/scripts/export_deploy_repo.ps1 -Target ..\Minsight-Deploy -Force -InitGit
```

The generated repo contains only `Core/` runtime slices and `Deploy/`. It
excludes `Lab/`, benchmark history, docs, PRD files, local `.env`, and local
SQLite files. Push that generated repository to GitHub, then clone it on ECS:

```bash
git clone <your-deploy-repo-url> /opt/minsight
cd /opt/minsight
sudo bash Deploy/scripts/bootstrap_aliyun.sh
```

## Docker Smoke Deploy

From the repository root:

```powershell
docker build -f Deploy/Dockerfile -t minsight-deploy .
docker run --rm -p 8788:8788 --env-file Deploy/.env.production.example -e MINSIGHT_DB_PATH=/data/minsight_deploy.sqlite -v minsight-deploy-data:/data minsight-deploy
```

Then verify the deploy boundary:

```powershell
python Deploy/scripts/smoke_check.py http://127.0.0.1:8788
```

The smoke check verifies:

- `/health` is reachable.
- demo cases can be listed.
- benchmark-only routes such as `/api/run`, `/api/runs`, and
  `/api/scenarios` are not exposed.

`Deploy/.env.production.example` is a template only. Replace model endpoint and
API key placeholders through your host secret manager before running real
extractions. The image mounts `/data` for the current SQLite prototype store;
Postgres is a later V4 hardening slice.

## Current Boundary

`Deploy/runtime.py` now owns the production-facing workbench lifecycle:

- create a meeting job
- run the formal Minsight Agent
- persist readable minutes, actions, decisions, and derived tasks
- sync tasks and decisions to Feishu sinks

It does not include benchmark run creation, LLM judge scoring, objective
metrics, V1 archives, or regression heatmaps.

`Deploy/runtime.py` now owns its SQLite workbench store through
`Deploy/store.py` and production Feishu adapters through `Deploy/integrations/`.
Lab remains out of the deploy Docker image and out of the runtime import path.

Next refactor target:

- Keep `Lab/` as an offline benchmark project only.
- Replace SQLite with Postgres for multi-user production.
- Replace in-memory background threads with a durable job queue.
