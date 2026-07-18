# -*- coding: utf-8 -*-
"""Feishu task sync adapters.

The default path is dry-run. Real writes go through lark-cli so auth, scopes,
and tokens stay outside application code.
"""

import json
import os
from pathlib import Path
from shutil import which
import subprocess


PROVIDER = "feishu"
LAB_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = LAB_ROOT.parent
_ENV_PATHS = [LAB_ROOT / ".env", WORKSPACE_ROOT / ".env"]
_ENV_LOADED = False


def load_local_env(force=False):
    """Load Lab/root .env values without overriding process-level env."""
    global _ENV_LOADED
    if _ENV_LOADED and not force:
        return None
    loaded_path = None
    for path in _ENV_PATHS:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        loaded_path = str(path)
        break
    _ENV_LOADED = True
    return loaded_path


def build_task_sink(mode=None, runner=None):
    load_local_env()
    selected = (mode or os.getenv("MINSIGHT_FEISHU_SYNC_MODE") or "dry_run").strip().lower()
    if selected in {"lark_cli", "lark-cli", "cli"}:
        return LarkCliTaskSink(runner=runner)
    return DryRunTaskSink()


def resolve_lark_cli_command():
    if os.name == "nt":
        return which("lark-cli.cmd") or which("lark-cli") or "lark-cli"
    return which("lark-cli") or "lark-cli"


def build_feishu_task_payload(task):
    title = str(task.get("title") or "").strip()
    assignee = str(task.get("assignee") or "").strip()
    evidence = str(task.get("source_evidence") or "").strip()
    due_date = task.get("due_date")
    description_lines = [
        "Created by Minsight from a structured meeting action item.",
    ]
    if assignee:
        description_lines.append(f"Assignee: {assignee}")
    if due_date:
        description_lines.append(f"Due: {due_date}")
    if evidence:
        description_lines.append("")
        description_lines.append("Evidence:")
        description_lines.append(evidence)
    payload = {
        "summary": title,
        "description": "\n".join(description_lines),
    }
    if due_date:
        payload["due"] = str(due_date)
    if task.get("id") is not None:
        payload["client_token"] = f"minsight-derived-task-{task['id']}"
    return payload


class DryRunTaskSink:
    provider = PROVIDER
    mode = "dry_run"

    def push_task(self, task):
        return {
            "provider": self.provider,
            "status": "dry_run",
            "external_id": None,
            "external_url": None,
            "payload": build_feishu_task_payload(task),
            "error": None,
        }


class LarkCliTaskSink:
    provider = PROVIDER
    mode = "lark_cli"

    def __init__(self, runner=None, identity=None, command=None):
        self.runner = runner or subprocess.run
        self.identity = identity or os.getenv("MINSIGHT_FEISHU_IDENTITY", "user")
        self.command = command or resolve_lark_cli_command()

    def push_task(self, task):
        payload = build_feishu_task_payload(task)
        command = [
            self.command,
            "task",
            "+create",
            "--as",
            self.identity,
            "--summary",
            payload["summary"],
        ]
        if payload.get("description"):
            command.extend(["--description", payload["description"]])
        if payload.get("due"):
            command.extend(["--due", payload["due"]])
        if payload.get("client_token"):
            command.extend(["--idempotency-key", payload["client_token"]])
        try:
            completed = self.runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except OSError as exc:
            return {
                "provider": self.provider,
                "status": "failed",
                "external_id": None,
                "external_url": None,
                "payload": payload,
                "error": str(exc),
            }
        if completed.returncode != 0:
            return {
                "provider": self.provider,
                "status": "failed",
                "external_id": None,
                "external_url": None,
                "payload": payload,
                "error": completed.stderr or completed.stdout or f"lark-cli exited {completed.returncode}",
            }
        data = _parse_cli_json(completed.stdout)
        external_id = _first_present(data, ("guid", "id", "task_guid"))
        external_url = _first_present(data, ("url", "app_link", "applink"))
        return {
            "provider": self.provider,
            "status": "synced",
            "external_id": external_id,
            "external_url": external_url,
            "payload": payload,
            "error": None,
        }


def _parse_cli_json(stdout):
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw": stdout}


def _first_present(value, keys):
    if isinstance(value, dict):
        for key in keys:
            if value.get(key):
                return value[key]
        for child in value.values():
            found = _first_present(child, keys)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _first_present(child, keys)
            if found:
                return found
    return None
