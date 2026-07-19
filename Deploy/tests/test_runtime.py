# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path
import sys

DEPLOY_ROOT = Path(__file__).resolve().parents[1]
if str(DEPLOY_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(DEPLOY_ROOT.parent))

from Deploy.runtime import WorkbenchRuntime


class SyncedTaskSink:
    mode = "lark_cli"

    def push_task(self, task):
        return {
            "provider": "feishu",
            "status": "synced",
            "external_id": "task-1",
            "external_url": "https://feishu.example/task-1",
            "payload": {"summary": task["title"]},
            "error": None,
        }


class SyncedDecisionSink:
    mode = "lark_cli"

    def push_decision(self, meeting, decision):
        return {
            "provider": "feishu_base",
            "status": "synced",
            "external_id": "record-1",
            "external_url": "https://feishu.example/base/record-1",
            "payload": {"Decision": decision["decision"]},
            "error": None,
        }


class DeployWorkbenchRuntimeTests(unittest.TestCase):
    def test_runtime_runs_workbench_without_benchmark_methods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "deploy.sqlite"

            def fake_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "Alice: ship the summary.",
                        "gold": {},
                    }
                ]

            def fake_v2(_case, _llm):
                return {
                    "participants": [{"name": "Alice", "role": "PM"}],
                    "key_points": [{"topic": "Launch", "summary": "Prepare launch note"}],
                    "action_items": [
                        {
                            "task": "Ship the summary",
                            "owner": "Alice",
                            "due": "2026-07-20",
                            "evidence": "Alice: ship the summary.",
                        }
                    ],
                    "decisions": [
                        {
                            "decision": "Use Minsight for launch notes",
                            "supersedes": None,
                            "evidence": "Alice: ship the summary.",
                        }
                    ],
                }

            runtime = WorkbenchRuntime(
                db_path=str(db_path),
                load_cases_fn=fake_cases,
                v2_extractor_factory=lambda _plain: ("langgraph", fake_v2),
                llm_factory=lambda: object(),
            )

            result = runtime.run_demo(title="Deploy demo", transcript="Alice: ship the summary.")

            self.assertEqual(result["meeting"]["status"], "completed")
            self.assertEqual(result["minutes"]["title"], "Deploy demo")
            self.assertEqual(result["derived_tasks"][0]["title"], "Ship the summary")
            self.assertEqual(result["decisions"][0]["decision"], "Use Minsight for launch notes")
            self.assertFalse(hasattr(runtime, "run_benchmark"))
            self.assertFalse(hasattr(runtime, "create_run"))
            self.assertFalse(hasattr(runtime, "list_runs"))

    def test_runtime_returns_frontend_field_contract_after_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "deploy.sqlite"

            def fake_v2(_case, _llm):
                return {
                    "participants": [],
                    "key_points": [],
                    "action_items": [
                        {
                            "task": "Send launch plan",
                            "owner": "Alice",
                            "due": "2026-07-20",
                            "evidence": "Alice: I will send the launch plan.",
                        }
                    ],
                    "decisions": [
                        {
                            "decision": "Use Base as decision archive",
                            "supersedes": None,
                            "evidence": "We will archive decisions in Base.",
                        }
                    ],
                }

            runtime = WorkbenchRuntime(
                db_path=str(db_path),
                load_cases_fn=lambda _scenario: [],
                v2_extractor_factory=lambda _plain: ("langgraph", fake_v2),
                llm_factory=lambda: object(),
                task_sink_factory=lambda mode=None: SyncedTaskSink(),
                decision_sink_factory=lambda mode=None: SyncedDecisionSink(),
            )
            created = runtime.run_demo(title="Contract demo", transcript="meeting transcript")
            meeting_id = created["meeting"]["meeting_id"]

            task_sync = runtime.sync_demo_tasks_to_feishu(meeting_id)
            decision_sync = runtime.sync_demo_decisions_to_feishu_base(meeting_id)
            details = runtime.get_demo_meeting_details(meeting_id)

            self.assertEqual(task_sync["mode"], "lark_cli")
            self.assertEqual(decision_sync["mode"], "lark_cli")
            self.assertEqual(details["derived_tasks"][0]["sync_status"], "synced")
            self.assertEqual(details["derived_tasks"][0]["external_url"], "https://feishu.example/task-1")
            self.assertIsNone(details["derived_tasks"][0]["sync_error"])
            self.assertEqual(details["decisions"][0]["base_sync_status"], "synced")
            self.assertEqual(details["decisions"][0]["base_url"], "https://feishu.example/base/record-1")

    def test_runtime_recovers_interrupted_meetings_on_startup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "deploy.sqlite"
            runtime = WorkbenchRuntime(db_path=str(db_path), load_cases_fn=lambda _scenario: [])
            running_id = runtime.create_demo_meeting(
                title="Interrupted",
                transcript="meeting transcript",
                scenario="demo",
            )
            completed_id = runtime.create_demo_meeting(
                title="Completed",
                transcript="meeting transcript",
                scenario="demo",
            )
            runtime.store().update_meeting(completed_id, status="completed", phase="completed")

            recovered = runtime.recover_interrupted_meetings()
            running = runtime.get_demo_meeting_details(running_id)["meeting"]
            completed = runtime.get_demo_meeting_details(completed_id)["meeting"]

            self.assertEqual(recovered, [running_id])
            self.assertEqual(running["status"], "failed")
            self.assertEqual(running["phase"], "interrupted")
            self.assertIn("server restarted", running["error_message"])
            self.assertEqual(completed["status"], "completed")


if __name__ == "__main__":
    unittest.main()
