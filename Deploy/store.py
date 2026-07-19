# -*- coding: utf-8 -*-
"""Deploy workbench persistence backed by SQLite."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


class WorkbenchStore:
    """SQLite store for deployable meeting workbench data only."""

    def __init__(self, path):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    meeting_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    scenario TEXT,
                    source_case_id TEXT,
                    transcript TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    error_message TEXT,
                    finished_at TEXT,
                    v1_json TEXT,
                    v2_json TEXT,
                    participants_json TEXT,
                    key_points_json TEXT,
                    comparison_json TEXT
                );

                CREATE TABLE IF NOT EXISTS meeting_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    task TEXT NOT NULL,
                    owner TEXT,
                    due TEXT,
                    evidence TEXT,
                    duplicate_group TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meeting_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    supersedes TEXT,
                    evidence TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS derived_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    action_id INTEGER,
                    title TEXT NOT NULL,
                    assignee TEXT,
                    due_date TEXT,
                    source_evidence TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_derived_task_columns(conn)
            self._ensure_meeting_decision_columns(conn)

    def _ensure_derived_task_columns(self, conn):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(derived_tasks)").fetchall()}
        additions = {
            "external_provider": "TEXT",
            "external_id": "TEXT",
            "external_url": "TEXT",
            "sync_status": "TEXT NOT NULL DEFAULT 'pending'",
            "sync_error": "TEXT",
            "sync_payload_json": "TEXT",
            "synced_at": "TEXT",
            "assignee_open_id": "TEXT",
            "assignee_resolution_status": "TEXT",
            "assignee_resolution_error": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE derived_tasks ADD COLUMN {name} {ddl}")

    def _ensure_meeting_decision_columns(self, conn):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(meeting_decisions)").fetchall()}
        additions = {
            "base_external_provider": "TEXT",
            "base_external_id": "TEXT",
            "base_external_url": "TEXT",
            "base_sync_status": "TEXT NOT NULL DEFAULT 'pending'",
            "base_sync_error": "TEXT",
            "base_sync_payload_json": "TEXT",
            "base_synced_at": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE meeting_decisions ADD COLUMN {name} {ddl}")

    def create_meeting(self, meeting_id, title, scenario, source_case_id, transcript):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO meetings(
                    meeting_id, title, scenario, source_case_id, transcript,
                    created_at, status, phase
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, title, scenario, source_case_id, transcript, _now(), "queued", "queued"),
            )

    def update_meeting(self, meeting_id, **fields):
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = [self._to_db_value(value) for value in fields.values()] + [meeting_id]
        with closing(self._connect()) as conn, conn:
            conn.execute(f"UPDATE meetings SET {columns} WHERE meeting_id = ?", values)

    def clear_meeting_assets(self, meeting_id):
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM meeting_actions WHERE meeting_id = ?", (meeting_id,))
            conn.execute("DELETE FROM meeting_decisions WHERE meeting_id = ?", (meeting_id,))
            conn.execute("DELETE FROM derived_tasks WHERE meeting_id = ?", (meeting_id,))

    def save_meeting_action(self, meeting_id, variant, task, owner, due, evidence, duplicate_group=None):
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO meeting_actions(
                    meeting_id, variant, task, owner, due, evidence, duplicate_group, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, variant, task, owner, due, evidence, duplicate_group, _now()),
            )
        return cur.lastrowid

    def save_meeting_decision(self, meeting_id, variant, decision, supersedes, evidence):
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO meeting_decisions(
                    meeting_id, variant, decision, supersedes, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, variant, decision, supersedes, evidence, _now()),
            )
        return cur.lastrowid

    def save_derived_task(self, meeting_id, action_id, title, assignee, due_date, source_evidence, status="open"):
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO derived_tasks(
                    meeting_id, action_id, title, assignee, due_date,
                    source_evidence, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, action_id, title, assignee, due_date, source_evidence, status, _now()),
            )
        return cur.lastrowid

    def list_meetings(self, limit=20):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT meeting_id, title, scenario, source_case_id, created_at,
                       status, phase, error_message, finished_at,
                       participants_json, key_points_json, comparison_json
                FROM meetings
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._decode_meeting_row(row) for row in rows]

    def get_meeting(self, meeting_id):
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT meeting_id, title, scenario, source_case_id, transcript,
                       created_at, status, phase, error_message, finished_at,
                       v1_json, v2_json, participants_json, key_points_json, comparison_json
                FROM meetings
                WHERE meeting_id = ?
                """,
                (meeting_id,),
            ).fetchone()
        return self._decode_meeting_row(row) if row else None

    def delete_meeting(self, meeting_id):
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM meeting_actions WHERE meeting_id = ?", (meeting_id,))
            conn.execute("DELETE FROM meeting_decisions WHERE meeting_id = ?", (meeting_id,))
            conn.execute("DELETE FROM derived_tasks WHERE meeting_id = ?", (meeting_id,))
            deleted = conn.execute("DELETE FROM meetings WHERE meeting_id = ?", (meeting_id,)).rowcount
        return deleted > 0

    def list_meeting_actions(self, meeting_id):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, meeting_id, variant, task, owner, due, evidence, duplicate_group, created_at
                FROM meeting_actions
                WHERE meeting_id = ?
                ORDER BY variant, id
                """,
                (meeting_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_meeting_decisions(self, meeting_id):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, meeting_id, variant, decision, supersedes, evidence, created_at,
                       base_external_provider, base_external_id, base_external_url,
                       base_sync_status, base_sync_error, base_sync_payload_json,
                       base_synced_at
                FROM meeting_decisions
                WHERE meeting_id = ?
                ORDER BY variant, id
                """,
                (meeting_id,),
            ).fetchall()
        return [self._decode_meeting_decision_row(row) for row in rows]

    def update_meeting_decision_sync(
        self,
        decision_id,
        provider,
        sync_status,
        external_id=None,
        external_url=None,
        sync_error=None,
        sync_payload=None,
    ):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE meeting_decisions
                SET base_external_provider = ?,
                    base_external_id = ?,
                    base_external_url = ?,
                    base_sync_status = ?,
                    base_sync_error = ?,
                    base_sync_payload_json = ?,
                    base_synced_at = ?
                WHERE id = ?
                """,
                (
                    provider,
                    external_id,
                    external_url,
                    sync_status,
                    sync_error,
                    json.dumps(sync_payload or {}, ensure_ascii=False),
                    _now(),
                    decision_id,
                ),
            )

    def list_derived_tasks(self, meeting_id):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, meeting_id, action_id, title, assignee, due_date,
                       source_evidence, status, created_at, external_provider,
                       external_id, external_url, sync_status, sync_error,
                       sync_payload_json, synced_at, assignee_open_id,
                       assignee_resolution_status, assignee_resolution_error
                FROM derived_tasks
                WHERE meeting_id = ?
                ORDER BY id
                """,
                (meeting_id,),
            ).fetchall()
        return [self._decode_derived_task_row(row) for row in rows]

    def update_derived_task_sync(
        self,
        task_id,
        provider,
        sync_status,
        external_id=None,
        external_url=None,
        sync_error=None,
        sync_payload=None,
        assignee_open_id=None,
        assignee_resolution_status=None,
        assignee_resolution_error=None,
    ):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE derived_tasks
                SET external_provider = ?,
                    external_id = ?,
                    external_url = ?,
                    sync_status = ?,
                    sync_error = ?,
                    sync_payload_json = ?,
                    synced_at = ?,
                    assignee_open_id = ?,
                    assignee_resolution_status = ?,
                    assignee_resolution_error = ?
                WHERE id = ?
                """,
                (
                    provider,
                    external_id,
                    external_url,
                    sync_status,
                    sync_error,
                    json.dumps(sync_payload or {}, ensure_ascii=False),
                    _now(),
                    assignee_open_id,
                    assignee_resolution_status,
                    assignee_resolution_error,
                    task_id,
                ),
            )

    def list_other_actions(self, meeting_id, variant="v2"):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, meeting_id, variant, task, owner, due, evidence, duplicate_group, created_at
                FROM meeting_actions
                WHERE meeting_id != ? AND variant = ?
                ORDER BY created_at DESC
                """,
                (meeting_id, variant),
            ).fetchall()
        return [dict(row) for row in rows]

    def _decode_meeting_row(self, row):
        if row is None:
            return None
        data = dict(row)
        for key in ("v1_json", "v2_json", "participants_json", "key_points_json", "comparison_json"):
            if key in data and data[key]:
                data[key] = json.loads(data[key])
            elif key in data:
                data[key] = None
        return data

    def _decode_derived_task_row(self, row):
        data = dict(row)
        if data.get("sync_payload_json"):
            data["sync_payload"] = json.loads(data["sync_payload_json"])
        else:
            data["sync_payload"] = None
        data.pop("sync_payload_json", None)
        return data

    def _decode_meeting_decision_row(self, row):
        data = dict(row)
        if data.get("base_sync_payload_json"):
            data["base_sync_payload"] = json.loads(data["base_sync_payload_json"])
        else:
            data["base_sync_payload"] = None
        data.pop("base_sync_payload_json", None)
        return data

    @staticmethod
    def _to_db_value(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value


def _now():
    return datetime.now(timezone.utc).isoformat()
