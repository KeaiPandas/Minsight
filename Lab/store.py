# -*- coding: utf-8 -*-
"""Lab persistence layer backed by SQLite."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


class BenchmarkStore:
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
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario TEXT,
                    v2_impl TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    impl TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    gold_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    context_json TEXT,
                    routing_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS judgements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

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
            self._ensure_run_columns(conn)
            self._ensure_prediction_columns(conn)
            self._ensure_derived_task_columns(conn)
            self._ensure_meeting_decision_columns(conn)

    def _ensure_run_columns(self, conn):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(benchmark_runs)").fetchall()}
        additions = {
            "status": "TEXT NOT NULL DEFAULT 'queued'",
            "phase": "TEXT NOT NULL DEFAULT 'queued'",
            "total_tasks": "INTEGER NOT NULL DEFAULT 0",
            "completed_tasks": "INTEGER NOT NULL DEFAULT 0",
            "current_case_id": "TEXT",
            "current_variant": "TEXT",
            "error_message": "TEXT",
            "finished_at": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE benchmark_runs ADD COLUMN {name} {ddl}")

    def _ensure_prediction_columns(self, conn):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(predictions)").fetchall()}
        if "context_json" not in cols:
            conn.execute("ALTER TABLE predictions ADD COLUMN context_json TEXT")

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

    def create_run(self, run_id, scenario, v2_impl):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO benchmark_runs(
                    run_id, scenario, v2_impl, created_at, status, phase,
                    total_tasks, completed_tasks
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, scenario, v2_impl, _now(), "queued", "queued", 0, 0),
            )

    def update_run_status(self, run_id, **fields):
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [run_id]
        with closing(self._connect()) as conn, conn:
            conn.execute(f"UPDATE benchmark_runs SET {columns} WHERE run_id = ?", values)

    def increment_completed_tasks(self, run_id, step=1):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE benchmark_runs
                SET completed_tasks = completed_tasks + ?
                WHERE run_id = ?
                """,
                (step, run_id),
            )

    def save_prediction(self, run_id, case_id, scenario, variant, impl, transcript, gold, output, routing, context=None):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO predictions(
                    run_id, case_id, scenario, variant, impl, transcript,
                    gold_json, output_json, context_json, routing_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_id,
                    scenario,
                    variant,
                    impl,
                    transcript,
                    json.dumps(gold, ensure_ascii=False),
                    json.dumps(output, ensure_ascii=False),
                    json.dumps(context or {}, ensure_ascii=False),
                    json.dumps(routing, ensure_ascii=False),
                    _now(),
                ),
            )

    def list_predictions(self, run_id):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT run_id, case_id, scenario, variant, impl,
                       transcript, gold_json, output_json, context_json, routing_json
                FROM predictions
                WHERE run_id = ?
                ORDER BY scenario, case_id, variant
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "case_id": row["case_id"],
                "scenario": row["scenario"],
                "variant": row["variant"],
                "impl": row["impl"],
                "transcript": row["transcript"],
                "gold": json.loads(row["gold_json"]),
                "output": json.loads(row["output_json"]),
                "context": json.loads(row["context_json"] or "{}"),
                "routing": json.loads(row["routing_json"]),
            }
            for row in rows
        ]

    def save_judgement(self, run_id, case_id, scenario, variant, result):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO judgements(run_id, case_id, scenario, variant, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_id,
                    scenario,
                    variant,
                    json.dumps(result, ensure_ascii=False),
                    _now(),
                ),
            )

    def list_runs(self, limit=20):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT run_id, scenario, v2_impl, created_at, status, phase,
                       total_tasks, completed_tasks, current_case_id, current_variant,
                       error_message, finished_at
                FROM benchmark_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_judgements(self, run_id):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT case_id, scenario, variant, raw_json, created_at
                FROM judgements
                WHERE run_id = ?
                ORDER BY scenario, case_id, variant
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "case_id": row["case_id"],
                "scenario": row["scenario"],
                "variant": row["variant"],
                "result": json.loads(row["raw_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_previous_v2_judgement(self, current_run_id, scenario, case_id):
        with closing(self._connect()) as conn:
            current = conn.execute(
                "SELECT created_at FROM benchmark_runs WHERE run_id = ?",
                (current_run_id,),
            ).fetchone()
            if not current:
                return None
            row = conn.execute(
                """
                SELECT j.run_id, j.case_id, j.scenario, j.variant, j.raw_json,
                       j.created_at, r.created_at AS run_created_at
                FROM judgements j
                JOIN benchmark_runs r ON r.run_id = j.run_id
                WHERE j.variant = 'v2'
                  AND j.scenario = ?
                  AND j.case_id = ?
                  AND j.run_id != ?
                  AND r.created_at < ?
                ORDER BY r.created_at DESC
                LIMIT 1
                """,
                (scenario, case_id, current_run_id, current["created_at"]),
            ).fetchone()
        if not row:
            return None
        return {
            "run_id": row["run_id"],
            "case_id": row["case_id"],
            "scenario": row["scenario"],
            "variant": row["variant"],
            "result": json.loads(row["raw_json"]),
            "created_at": row["created_at"],
            "run_created_at": row["run_created_at"],
        }

    def get_previous_run(self, current_run_id, scenario):
        """Return the latest completed run before current_run_id for the same scenario."""
        with closing(self._connect()) as conn:
            current = conn.execute(
                "SELECT created_at FROM benchmark_runs WHERE run_id = ?",
                (current_run_id,),
            ).fetchone()
            if not current:
                return None
            if scenario is None:
                row = conn.execute(
                    """
                    SELECT run_id, scenario, v2_impl, created_at AS run_created_at
                    FROM benchmark_runs
                    WHERE run_id != ?
                      AND scenario IS NULL
                      AND status = 'completed'
                      AND created_at < ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (current_run_id, current["created_at"]),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT run_id, scenario, v2_impl, created_at AS run_created_at
                    FROM benchmark_runs
                    WHERE run_id != ?
                      AND scenario = ?
                      AND status = 'completed'
                      AND created_at < ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (current_run_id, scenario, current["created_at"]),
                ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id):
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT run_id, scenario, v2_impl, created_at, status, phase,
                       total_tasks, completed_tasks, current_case_id, current_variant,
                       error_message, finished_at
                FROM benchmark_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_run(self, run_id):
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM judgements WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM predictions WHERE run_id = ?", (run_id,))
            deleted = conn.execute(
                "DELETE FROM benchmark_runs WHERE run_id = ?",
                (run_id,),
            ).rowcount
        return deleted > 0

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
            deleted = conn.execute(
                "DELETE FROM meetings WHERE meeting_id = ?",
                (meeting_id,),
            ).rowcount
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
