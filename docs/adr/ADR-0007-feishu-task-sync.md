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

## Consequences

- Demo safety improves because the default path is dry-run.
- Real Feishu writes are opt-in and delegated to `lark-cli`.
- Frontend and API can explain sync failures without losing local meeting data.
- On Windows, the adapter resolves the `lark-cli.cmd` shim first because Python
  subprocesses cannot always execute the PowerShell shim directly.
- CLI startup errors, permission errors, and non-zero exits are persisted as
  task-level `failed` states instead of causing HTTP 500.
- Assignment is intentionally conservative in this iteration: assignee names are
  written into the task description, not converted to Feishu members, because
  real assignment requires reliable open_id/user_id resolution.

## Follow-Ups

- Add optional Feishu contact resolution for assignee names.
- Add tasklist selection once the target tasklist workflow is stable.
- Consider syncing decisions to a Feishu document or Base table in a later phase.

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
