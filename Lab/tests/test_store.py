# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path
import sys

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from store import BenchmarkStore


class BenchmarkStoreTests(unittest.TestCase):
    def test_store_persists_run_prediction_and_judgement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            store = BenchmarkStore(str(db_path))
            store.init_schema()

            store.create_run("run-1", "decision_reversal", "langgraph")
            store.update_run_status(
                "run-1",
                status="running",
                phase="predictions",
                total_tasks=4,
                completed_tasks=1,
            )
            store.save_prediction(
                run_id="run-1",
                case_id="case-1",
                scenario="decision_reversal",
                variant="v2",
                impl="langgraph",
                transcript="hello",
                gold={"participants": []},
                output={"participants": []},
                routing=[{"agent": "normalize"}],
            )
            store.save_judgement(
                run_id="run-1",
                case_id="case-1",
                scenario="decision_reversal",
                variant="v2",
                result={
                    "participants": 1.0,
                    "key_points": 1.0,
                    "action_items": 1.0,
                    "decisions": 1.0,
                    "overall": 1.0,
                    "summary": "ok",
                    "strengths": [],
                    "issues": [],
                },
            )

            run = store.get_run("run-1")
            predictions = store.list_predictions("run-1")
            judgements = store.list_judgements("run-1")

            self.assertEqual(run["status"], "running")
            self.assertEqual(run["phase"], "predictions")
            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0]["variant"], "v2")
            self.assertEqual(len(judgements), 1)
            self.assertEqual(judgements[0]["result"]["overall"], 1.0)

    def test_delete_run_removes_run_predictions_and_judgements(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            store = BenchmarkStore(str(db_path))
            store.init_schema()

            store.create_run("run-1", "decision_reversal", "langgraph")
            store.save_prediction(
                run_id="run-1",
                case_id="case-1",
                scenario="decision_reversal",
                variant="v1",
                impl="single-call",
                transcript="hello",
                gold={"participants": []},
                output={"participants": []},
                routing=[],
            )
            store.save_judgement(
                run_id="run-1",
                case_id="case-1",
                scenario="decision_reversal",
                variant="v1",
                result={
                    "participants": 0.0,
                    "key_points": 0.0,
                    "action_items": 0.0,
                    "decisions": 0.0,
                    "overall": 0.0,
                    "summary": "empty",
                    "strengths": [],
                    "issues": [],
                },
            )

            self.assertTrue(store.delete_run("run-1"))
            self.assertIsNone(store.get_run("run-1"))
            self.assertEqual(store.list_predictions("run-1"), [])
            self.assertEqual(store.list_judgements("run-1"), [])

    def test_get_previous_run_returns_latest_completed_run_with_same_scenario(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            store = BenchmarkStore(str(db_path))
            store.init_schema()

            store.create_run("older-same", "demo", "langgraph")
            store.create_run("newer-other", "other", "langgraph")
            store.create_run("current", "demo", "langgraph")
            store.update_run_status("older-same", created_at="2026-07-18T01:00:00+00:00", status="completed")
            store.update_run_status("newer-other", created_at="2026-07-18T02:00:00+00:00", status="completed")
            store.update_run_status("current", created_at="2026-07-18T03:00:00+00:00", status="completed")

            previous = store.get_previous_run("current", "demo")

            self.assertEqual(previous["run_id"], "older-same")
            self.assertEqual(previous["run_created_at"], "2026-07-18T01:00:00+00:00")

    def test_store_persists_meeting_assets_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            store = BenchmarkStore(str(db_path))
            store.init_schema()

            store.create_meeting(
                meeting_id="meeting-1",
                title="Weekly review",
                scenario="decision_reversal",
                source_case_id="rev_01",
                transcript="meeting transcript",
            )
            store.update_meeting(
                "meeting-1",
                status="completed",
                phase="completed",
                v2_json={"action_items": [{"task": "Ship"}]},
                comparison_json={"highlights": ["V2 recovered"]},
            )
            action_id = store.save_meeting_action(
                meeting_id="meeting-1",
                variant="v2",
                task="Ship review doc",
                owner="Alice",
                due="2026-07-20",
                evidence="Alice: I will ship it.",
                duplicate_group="alice::ship review doc",
            )
            store.save_meeting_decision(
                meeting_id="meeting-1",
                variant="v2",
                decision="Delay launch",
                supersedes="Launch Friday",
                evidence="Delay it.",
            )
            store.save_derived_task(
                meeting_id="meeting-1",
                action_id=action_id,
                title="Ship review doc",
                assignee="Alice",
                due_date="2026-07-20",
                source_evidence="Alice: I will ship it.",
            )

            meeting = store.get_meeting("meeting-1")
            actions = store.list_meeting_actions("meeting-1")
            decisions = store.list_meeting_decisions("meeting-1")
            tasks = store.list_derived_tasks("meeting-1")

            self.assertEqual(meeting["status"], "completed")
            self.assertEqual(meeting["comparison_json"]["highlights"][0], "V2 recovered")
            self.assertEqual(actions[0]["task"], "Ship review doc")
            self.assertEqual(decisions[0]["supersedes"], "Launch Friday")
            self.assertEqual(tasks[0]["assignee"], "Alice")
