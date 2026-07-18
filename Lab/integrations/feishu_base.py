# -*- coding: utf-8 -*-
"""Feishu Base decision sync adapters."""

import json
import os
import subprocess

from integrations.feishu_tasks import load_local_env, resolve_lark_cli_command


PROVIDER = "feishu_base"


def build_decision_sink(mode=None, runner=None):
    load_local_env()
    selected = (mode or os.getenv("MINSIGHT_FEISHU_BASE_SYNC_MODE") or os.getenv("MINSIGHT_FEISHU_SYNC_MODE") or "dry_run").strip().lower()
    if selected in {"lark_cli", "lark-cli", "cli"}:
        return LarkCliBaseDecisionSink(
            runner=runner,
            identity=os.getenv("MINSIGHT_FEISHU_IDENTITY", "user"),
            base_token=os.getenv("MINSIGHT_FEISHU_BASE_TOKEN") or None,
            table_id=os.getenv("MINSIGHT_FEISHU_DECISIONS_TABLE_ID") or None,
            workspace_url=os.getenv("MINSIGHT_FEISHU_BASE_WORKSPACE_URL") or None,
        )
    return DryRunDecisionSink()


def build_decision_payload(meeting, decision):
    return {
        "Decision ID": f"{meeting.get('meeting_id')}:{decision.get('id')}",
        "Meeting ID": meeting.get("meeting_id") or "",
        "Meeting Title": meeting.get("title") or "",
        "Scenario": meeting.get("scenario") or "",
        "Decision": decision.get("decision") or "",
        "Supersedes": decision.get("supersedes") or "",
        "Evidence": decision.get("evidence") or "",
        "Created At": decision.get("created_at") or "",
    }


class DryRunDecisionSink:
    provider = PROVIDER
    mode = "dry_run"

    def push_decision(self, meeting, decision):
        return {
            "provider": self.provider,
            "status": "dry_run",
            "external_id": None,
            "external_url": None,
            "payload": build_decision_payload(meeting, decision),
            "error": None,
        }


class LarkCliBaseDecisionSink:
    provider = PROVIDER
    mode = "lark_cli"

    def __init__(self, runner=None, identity=None, command=None, base_token=None, table_id=None, workspace_url=None):
        self.runner = runner or subprocess.run
        self.identity = identity or os.getenv("MINSIGHT_FEISHU_IDENTITY", "user")
        self.command = command or resolve_lark_cli_command()
        self.base_token = base_token
        self.table_id = table_id
        self.workspace_url = workspace_url

    def push_decision(self, meeting, decision):
        payload = build_decision_payload(meeting, decision)
        missing = []
        if not self.base_token:
            missing.append("MINSIGHT_FEISHU_BASE_TOKEN")
        if not self.table_id:
            missing.append("MINSIGHT_FEISHU_DECISIONS_TABLE_ID")
        if missing:
            extra = f"; workspace={self.workspace_url}" if self.workspace_url else ""
            return {
                "provider": self.provider,
                "status": "failed",
                "external_id": None,
                "external_url": None,
                "payload": payload,
                "error": f"missing Base configuration: {', '.join(missing)}{extra}",
            }
        command = [
            self.command,
            "base",
            "+record-upsert",
            "--as",
            self.identity,
            "--base-token",
            self.base_token,
            "--table-id",
            self.table_id,
            "--json",
            json.dumps(payload, ensure_ascii=False),
        ]
        if decision.get("base_external_id"):
            command.extend(["--record-id", decision["base_external_id"]])
        try:
            completed = self.runner(command, capture_output=True, text=True, encoding="utf-8")
        except OSError as exc:
            return _result("failed", payload, error=str(exc))
        if completed.returncode != 0:
            return _result("failed", payload, error=completed.stderr or completed.stdout)
        data = _parse_cli_json(completed.stdout)
        return _result(
            "synced",
            payload,
            external_id=_first_present(data, ("record_id", "id")),
            external_url=_first_present(data, ("record_url", "url", "share_url")),
        )


def _result(status, payload, external_id=None, external_url=None, error=None):
    return {
        "provider": PROVIDER,
        "status": status,
        "external_id": external_id,
        "external_url": external_url,
        "payload": payload,
        "error": error,
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
