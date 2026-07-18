# Minsight Lab

`Lab/` now serves two purposes:

1. `Benchmark`
   Run the formal Minsight Agent against the shared scenario set, persist predictions, score them with deterministic objective metrics plus LLM semantic judge, and compare each case with the previous run of the same task.
2. `Workbench`
   Run a real transcript or mock case through V2, persist meeting assets, show readable minutes, evidence, derived tasks, and cross-meeting alerts.

## Public Seams

The Lab critical path is organized around three public seams:

1. `HTTP API`
   Exposed by [server.py](/D:/Interview/Minsight/Lab/server.py)
2. `Runtime`
   Owned by [runtime.py](/D:/Interview/Minsight/Lab/runtime.py)
3. `SQLite store`
   Implemented by [store.py](/D:/Interview/Minsight/Lab/store.py)

Supporting modules:

- [judge.py](/D:/Interview/Minsight/Lab/judge.py)
  LLM judge for semantic benchmark dimensions
- [metrics.py](/D:/Interview/Minsight/Lab/metrics.py)
  Deterministic objective metrics for participants and action items
- [web/](/D:/Interview/Minsight/Lab/web)
  Static frontend for both workbench and benchmark views

## What The Workbench Adds

The workbench demo closes the business loop that the benchmark view does not:

- transcript input or mock case selection
- direct V2 execution for the business-facing demo
- human-readable meeting minutes
- evidence display for action items and decisions
- `action_items -> derived_tasks` persistence
- manual `derived_tasks -> Feishu Tasks` sync through dry-run or `lark-cli`
- cross-meeting duplicate-task hints

SQLite now stores lightweight business assets in addition to benchmark records:

- `meetings`
- `meeting_actions`
- `meeting_decisions`
- `derived_tasks`

`derived_tasks` also stores Feishu sync state:

- `sync_status`: `pending`, `dry_run`, `synced`, or `failed`
- `external_provider`, `external_id`, `external_url`
- `sync_error`, `sync_payload`, `synced_at`

## Benchmark Basis

Benchmark cases are loaded from `Core/data/scenarios/*.json`.
Each case has a human-authored `gold` answer for:

- `participants`
- `key_points`
- `action_items`
- `decisions`

Gold annotations follow [annotation_rubric.md](/D:/Interview/Minsight/docs/annotation_rubric.md), including topic-level decision boundaries and verbatim evidence requirements.

The current scenarios intentionally cover different failure modes:

| Scenario | Purpose |
|---|---|
| `decision_reversal` | Decision reversal and `supersedes`. |
| `long_meeting` | Long context and late corrections. |
| `missing_fields` | Missing owner/due fields and anti-hallucination. |
| `mixed_language` | Chinese-English mixed terms. |
| `multi_topic` | Topic switching and parking-lot filtering. |
| `nickname_reference` | Nickname/reference resolution. |
| `real_world_kickoff` | Long real-world prioritization and scope-cut meeting. |

Scores shown in the UI come from a hybrid evaluation path:

1. Lab runs the formal Minsight Agent on the selected case set.
2. Predictions, `gold`, and lightweight case context such as `meeting_info` are persisted to SQLite.
3. `metrics.py` deterministically scores objective dimensions:
   `participants` and `action_items`.
4. `judge.py` sends `transcript + gold + prediction` to the fixed judge prompt for semantic dimensions:
   `key_points` and `decisions`.
5. Lab combines objective and semantic scores into the final `overall`.
6. The frontend renders them as percentages.
7. If the same scenario/case has a previous V2 run, the frontend shows a heatmap of current score minus previous score.

No embedding similarity API is used in the current benchmark flow.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the web console:

```bash
python server.py
```

Then open:

```text
http://127.0.0.1:8787
```

The default landing tab is `Workbench`. The second tab is `Benchmark`.

You can still run benchmark-only CLI mode:

```bash
python run.py --scenario decision_reversal
```

## API Surface

Benchmark APIs:

- `GET /api/scenarios`
- `GET /api/runs`
- `POST /api/run`
- `GET /api/run?id=<run_id>`
- `DELETE /api/run?id=<run_id>`

Workbench APIs:

- `GET /api/demo/cases`
- `GET /api/demo/meetings`
- `POST /api/demo/run`
- `GET /api/demo/meeting?id=<meeting_id>`
- `POST /api/demo/meeting/sync-feishu`

## Feishu Task Sync

Workbench task sync is manual. Runtime loads local settings from `Lab/.env`
first, then from the repository root `.env`. Shell environment variables still
take precedence.

Safe preview mode:

```powershell
$env:MINSIGHT_FEISHU_SYNC_MODE="dry_run"
```

Or write it into `Lab/.env`:

```env
MINSIGHT_FEISHU_SYNC_MODE=dry_run
MINSIGHT_FEISHU_IDENTITY=user
```

To write through local `lark-cli` after you have configured auth and scopes:

```powershell
$env:MINSIGHT_FEISHU_SYNC_MODE="lark_cli"
$env:MINSIGHT_FEISHU_IDENTITY="user"
```

Equivalent `Lab/.env`:

```env
MINSIGHT_FEISHU_SYNC_MODE=lark_cli
MINSIGHT_FEISHU_IDENTITY=user
MINSIGHT_FEISHU_RESOLVE_ASSIGNEE=false
```

The adapter calls the safer `lark-cli task +create` shortcut and passes
`--idempotency-key minsight-derived-task-<id>` so repeated clicks do not create
duplicate tasks for the same derived task.

The workbench also treats sync as a stateful operation:

- `pending`, `dry_run`, `synced`, and `failed` tasks can be filtered in the UI.
- Synced tasks show the Feishu task link, external id, sync time, and stored
  payload.
- Failed tasks show the CLI/API error captured in `sync_error`.
- A second sync skips already synced tasks by default. If the user confirms a
  force sync in the UI, the API receives `force=true` and retries those tasks
  using the same idempotency key.
- Assignee resolution is disabled by default so task sync does not require
  contact scopes. If enabled, it searches Feishu contacts and passes
  `--assignee <open_id>` when there is exactly one match:

```env
MINSIGHT_FEISHU_RESOLVE_ASSIGNEE=true
```

Keep it `false` for the lowest-friction demo path. With this setting, assignee
names are preserved in the Feishu task description and no contact lookup is
performed.

- Tasklist routing can be configured by env or entered in the workbench UI:

```env
MINSIGHT_FEISHU_TASKLIST_ID=<tasklist-guid-or-url>
```

On Windows the adapter resolves the `lark-cli.cmd` shim first because Python
subprocesses cannot always execute the PowerShell shim directly. If the CLI is
missing, unauthenticated, or exits with an error, the sync API records the task
as `failed` instead of returning HTTP 500.

Check the active CLI identity before real sync:

```powershell
lark-cli auth status
```

If `MINSIGHT_FEISHU_IDENTITY=user`, `auth status` must show an available user
token. If it says only bot/tenant identity is available, run user authorization:

```powershell
lark-cli auth login --scope "task:task:write"
```

Alternatively set `MINSIGHT_FEISHU_IDENTITY=bot` if you want the configured app
identity to create tasks and the app has the required task scope.

Required Feishu scope for real task creation:

```text
task:task:write
```

Additional scope only when `MINSIGHT_FEISHU_RESOLVE_ASSIGNEE=true`:

```text
contact:user:search
```

The first integration keeps assignee names in the task description instead of
assigning Feishu members directly unless contact resolution returns a single
clear `open_id`. Ambiguous, missing, or permission-denied contact results are
recorded on the task and do not block task creation.

## Feishu Base Decision Sync

Meeting decisions can be synced into a Feishu Base table from the workbench.
The sync is manual, stateful, and mirrors task sync behavior: already synced
decisions are skipped by default, while the UI can send `force=true` to retry.

Required configuration for real writes:

```env
MINSIGHT_FEISHU_BASE_SYNC_MODE=lark_cli
MINSIGHT_FEISHU_BASE_TOKEN=<base-token>
MINSIGHT_FEISHU_DECISIONS_TABLE_ID=<table-id-or-table-name>
```

The workspace URL can be kept as operator context, but it is not enough to write
records:

```env
MINSIGHT_FEISHU_BASE_WORKSPACE_URL=https://my.feishu.cn/base/workspace/...
```

The decision table should contain writable text fields matching these names:

- `Decision ID`
- `Meeting ID`
- `Meeting Title`
- `Scenario`
- `Decision`
- `Supersedes`
- `Evidence`
- `Created At`

If `MINSIGHT_FEISHU_BASE_TOKEN` or `MINSIGHT_FEISHU_DECISIONS_TABLE_ID` is
missing, the sync result is recorded as `failed` with an actionable
configuration error instead of returning HTTP 500.

## Outputs

SQLite file:

- `minsight_lab.sqlite`
  Benchmark records plus workbench meeting assets

Benchmark artifacts:

- `results/<run_id>.json`
  Aggregated benchmark summary for a completed run

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```

The automated coverage now protects:

- benchmark store persistence
- benchmark runtime lifecycle
- workbench meeting asset persistence
- Feishu task sync dry-run and lark-cli adapter behavior
- Feishu contact resolution as an opt-in adapter
- Feishu Base decision sync dry-run and lark-cli adapter behavior
- benchmark HTTP flow
- workbench HTTP flow
- scenario fixture complexity and gold coverage
