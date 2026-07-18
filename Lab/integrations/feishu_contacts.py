# -*- coding: utf-8 -*-
"""Feishu contact resolution through lark-cli."""

import json
import os
import subprocess
from shutil import which


def resolve_lark_cli_command():
    if os.name == "nt":
        return which("lark-cli.cmd") or which("lark-cli") or "lark-cli"
    return which("lark-cli") or "lark-cli"


class LarkCliContactResolver:
    def __init__(self, runner=None, identity=None, command=None):
        self.runner = runner or subprocess.run
        self.identity = identity or os.getenv("MINSIGHT_FEISHU_IDENTITY", "user")
        self.command = command or resolve_lark_cli_command()

    def resolve(self, query):
        name = str(query or "").strip()
        if not name:
            return _resolution("skipped", error="empty assignee")
        command = [
            self.command,
            "contact",
            "+search-user",
            "--as",
            self.identity,
            "--query",
            name,
            "--page-size",
            "10",
        ]
        try:
            completed = self.runner(command, capture_output=True, text=True, encoding="utf-8")
        except OSError as exc:
            return _resolution("failed", error=str(exc))
        if completed.returncode != 0:
            return _resolution("failed", error=completed.stderr or completed.stdout)
        users = _extract_users(_parse_json(completed.stdout))
        if not users:
            return _resolution("not_found")
        if len(users) > 1:
            return _resolution("ambiguous", candidates=users)
        user = users[0]
        open_id = user.get("open_id") or user.get("user_open_id") or user.get("userOpenId") or user.get("id")
        return _resolution("resolved", open_id=open_id, candidates=users)


def _resolution(status, open_id=None, candidates=None, error=None):
    return {
        "status": status,
        "open_id": open_id,
        "candidates": candidates or [],
        "error": error,
    }


def _parse_json(stdout):
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw": stdout}


def _extract_users(value):
    if isinstance(value, dict):
        if isinstance(value.get("users"), list):
            return [_compact_user(user) for user in value["users"]]
        if isinstance(value.get("items"), list):
            return [_compact_user(user) for user in value["items"]]
        for child in value.values():
            users = _extract_users(child)
            if users:
                return users
    if isinstance(value, list):
        return [_compact_user(user) for user in value if isinstance(user, dict)]
    return []


def _compact_user(user):
    return {
        key: user.get(key)
        for key in ("open_id", "user_open_id", "userOpenId", "id", "name", "email")
        if user.get(key)
    }
