# ADR-0007: Add Feishu Task Sync Through Lab Integration Sink

- Date: 2026-07-18
- Status: Accepted

## Context

Minsight already turns meeting action items into local `derived_tasks`.
To make the workbench demo closer to a real meeting productivity loop, those
derived tasks need a path into Feishu/Lark.

The integration must not make Core depend on Feishu APIs. Core should remain the
structured extraction engine, while Lab owns demo persistence and external
system synchronization.

## Decision

Add a Lab-side task sync seam:

```text
Core V2 structured output
  -> Lab derived_tasks
  -> TaskSink
      -> DryRunTaskSink
      -> LarkCliTaskSink
```

The first supported sync target is Feishu Tasks:

- `DryRunTaskSink` is the default and never writes to Feishu.
- `LarkCliTaskSink` shells out to `lark-cli task +create --as <identity>`.
- Authentication, app secrets, user login, and scopes stay in `lark-cli`; the
  Minsight codebase does not store Feishu tokens.
- The workbench exposes a manual "Sync to Feishu" action instead of syncing
  automatically after every extraction run.
- Each sync uses `--idempotency-key minsight-derived-task-<id>` so repeated
  clicks for the same local derived task do not create duplicate Feishu tasks.
- Already synced local tasks are skipped by default. The UI asks for explicit
  confirmation before sending `force=true` to retry those tasks.
- Assignee names can be resolved through `lark-cli contact +search-user` only
  when `MINSIGHT_FEISHU_RESOLVE_ASSIGNEE=true`; a single clear match is passed
  to `task +create --assignee <open_id>`.
- A tasklist target can be supplied from `MINSIGHT_FEISHU_TASKLIST_ID` or the
  workbench UI and is passed to `task +create --tasklist-id`.
- Meeting decisions sync through a separate `DecisionSink` into Feishu Base via
  `lark-cli base +record-upsert` when `MINSIGHT_FEISHU_BASE_TOKEN` and
  `MINSIGHT_FEISHU_DECISIONS_TABLE_ID` are configured.

## Configuration

Default:

```powershell
$env:MINSIGHT_FEISHU_SYNC_MODE="dry_run"
```

Real CLI writes:

```powershell
$env:MINSIGHT_FEISHU_SYNC_MODE="lark_cli"
$env:MINSIGHT_FEISHU_IDENTITY="user"
```

Local demo runs can also put the same settings in `Lab/.env`, which is ignored
by git. Runtime reads `Lab/.env` first, then the repository root `.env`, while
already-exported shell environment variables keep precedence.

The expected Feishu scope for real task creation is `task:task:write`.
Assignee resolution is disabled by default. Enabling it requires the additional
`contact:user:search` scope.

For `MINSIGHT_FEISHU_IDENTITY=user`, `lark-cli auth status` must show a valid
user token. If only bot/tenant identity is available, run:

```powershell
lark-cli auth login --scope "task:task:write"
```

For `MINSIGHT_FEISHU_IDENTITY=bot`, the Feishu app must have the task write
scope enabled in the developer console.

## Persistence

`derived_tasks` now stores sync state:

- `external_provider`
- `external_id`
- `external_url`
- `sync_status`
- `sync_error`
- `sync_payload`
- `synced_at`

This lets the workbench show whether a local task is still pending, dry-run
previewed, synced, or failed.

The workbench renders these states as a filterable task board and shows the
external task link, external id, sync timestamp, payload, or captured error
where available.

`meeting_decisions` stores Base sync state separately:

- `base_external_provider`
- `base_external_id`
- `base_external_url`
- `base_sync_status`
- `base_sync_error`
- `base_sync_payload`
- `base_synced_at`

## Consequences

- Demo safety improves because the default path is dry-run.
- Real Feishu writes are opt-in and delegated to `lark-cli`.
- Frontend and API can explain sync failures without losing local meeting data.
- On Windows, the adapter resolves the `lark-cli.cmd` shim first because Python
  subprocesses cannot always execute the PowerShell shim directly.
- CLI startup errors, permission errors, and non-zero exits are persisted as
  task-level `failed` states instead of causing HTTP 500.
- Repeated sync attempts are safer: the backend skips `synced` tasks unless
  `force=true`, and forced retries still use the same idempotency key.
- Assignment is an optional enhancement, disabled by default to keep the demo
  path on `task:task:write` only. When explicitly enabled, ambiguous, missing,
  or permission-denied contact lookup results are recorded and the task still
  syncs without `--assignee`.
- The provided Base workspace URL is treated as operator context, not as a
  writable `base_token`. Real decision writes require explicit Base/table
  configuration to avoid writing to the wrong object.

## Follow-Ups

- Add a UI hint for enabling Feishu contact resolution after the user grants
  `contact:user:search`.
- Add automatic Base/table bootstrap once the workspace-to-base creation flow is
  fully confirmed.
- Add richer tasklist discovery once list/search UX is worth the extra scope.

## Validation

Covered by:

- `Lab/tests/test_feishu_tasks.py`
- `Lab/tests/test_store.py`
- `Lab/tests/test_runtime.py`
- `Lab/tests/test_server.py`

Run:

```powershell
python -m unittest discover -s D:\Interview\Minsight\Lab\tests -v
```

Manual validation on 2026-07-18:

- `Lab/.env` set to `MINSIGHT_FEISHU_SYNC_MODE=lark_cli`.
- `lark-cli task +create --dry-run` produced the expected Feishu Task API body.
- Workbench "Sync to Feishu" was confirmed successful by the user.
- A Feishu Base named `Minsight 决策库` was created for decision sync, with a
  `Decisions` table containing the required decision traceability fields.
- `lark-cli base +record-upsert --dry-run` produced the expected Feishu Base
  record API body for the `Decisions` table.
- Contact lookup failures caused by missing `contact:user:search` were handled
  by changing assignee resolution into an explicit opt-in enhancement rather
  than part of the default sync path.
