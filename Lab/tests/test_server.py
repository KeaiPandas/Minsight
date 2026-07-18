# -*- coding: utf-8 -*-

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from server import build_handler
from runtime import BenchmarkRuntime
from integrations.feishu_tasks import DryRunTaskSink
from integrations.feishu_base import DryRunDecisionSink


class ServerApiTests(unittest.TestCase):
    def test_http_api_exposes_scenarios_and_accepts_run_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            results_dir = Path(tmpdir) / "results"

            def fake_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "meeting transcript",
                        "gold": {"participants": []},
                    }
                ]

            def fake_extract(case, _llm):
                return {"case_id": case["id"]}

            def fake_judge(**_kwargs):
                return {
                    "participants": 1.0,
                    "key_points": 1.0,
                    "action_items": 1.0,
                    "decisions": 1.0,
                    "overall": 1.0,
                    "summary": "ok",
                    "strengths": [],
                    "issues": [],
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(results_dir),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["demo"],
                v2_extractor_factory=lambda plain: ("langgraph", fake_extract),
                judge_fn=fake_judge,
                llm_factory=lambda: object(),
            )

            handler = build_handler(runtime)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                scenarios = json.loads(
                    urllib.request.urlopen(f"{base_url}/api/scenarios").read().decode("utf-8")
                )
                self.assertEqual(scenarios["scenarios"], ["demo"])

                request = urllib.request.Request(
                    f"{base_url}/api/run",
                    data=json.dumps({"scenario": "demo"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                payload = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
                self.assertEqual(payload["status"], "queued")

                deadline = time.time() + 3
                run_payload = None
                while time.time() < deadline:
                    run_payload = json.loads(
                        urllib.request.urlopen(
                            f"{base_url}/api/run?id={payload['run_id']}"
                        ).read().decode("utf-8")
                    )
                    if run_payload["run"]["status"] == "completed":
                        break
                    time.sleep(0.1)

                self.assertIsNotNone(run_payload)
                self.assertEqual(run_payload["run"]["status"], "completed")
            finally:
                server.shutdown()
                server.server_close()

    def test_http_api_deletes_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=lambda _scenario: [],
                list_scenarios_fn=lambda: ["demo"],
                v2_extractor_factory=lambda plain: ("langgraph", lambda case, _llm: case),
                judge_fn=lambda **_kwargs: {},
                llm_factory=lambda: object(),
            )
            runtime.store().create_run("run-1", "demo", "langgraph")

            handler = build_handler(runtime)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                request = urllib.request.Request(
                    f"{base_url}/api/run?id=run-1",
                    method="DELETE",
                )
                payload = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
                self.assertTrue(payload["deleted"])

                with self.assertRaises(Exception):
                    urllib.request.urlopen(f"{base_url}/api/run?id=run-1")
            finally:
                server.shutdown()
                server.server_close()

    def test_http_api_exposes_demo_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"

            def fake_load_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "meeting transcript",
                        "gold": {"participants": []},
                    }
                ]

            def fake_v2(_case, _llm):
                return {
                    "participants": [{"name": "Alice", "role": "PM"}],
                    "key_points": [{"topic": "Launch", "summary": "Delay launch"}],
                    "action_items": [
                        {
                            "task": "Ship review doc",
                            "owner": "Alice",
                            "due": "2026-07-20",
                            "evidence": "Alice: I will ship it.",
                        }
                    ],
                    "decisions": [
                        {
                            "decision": "Delay launch",
                            "supersedes": "Launch Friday",
                            "evidence": "Delay it.",
                        }
                    ],
                    "_format_valid": True,
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_load_cases,
                list_scenarios_fn=lambda: ["demo"],
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                llm_factory=lambda: object(),
                task_sink_factory=lambda mode=None: DryRunTaskSink(),
                decision_sink_factory=lambda mode=None: DryRunDecisionSink(),
            )

            handler = build_handler(runtime)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                cases = json.loads(
                    urllib.request.urlopen(f"{base_url}/api/demo/cases").read().decode("utf-8")
                )
                self.assertEqual(cases["cases"][0]["case_id"], "case-1")

                request = urllib.request.Request(
                    f"{base_url}/api/demo/run",
                    data=json.dumps({"title": "Weekly review", "transcript": "meeting transcript"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                payload = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
                self.assertEqual(payload["status"], "queued")

                deadline = time.time() + 3
                meeting_payload = None
                while time.time() < deadline:
                    meeting_payload = json.loads(
                        urllib.request.urlopen(
                            f"{base_url}/api/demo/meeting?id={payload['meeting_id']}"
                        ).read().decode("utf-8")
                    )
                    if meeting_payload["meeting"]["status"] == "completed":
                        break
                    time.sleep(0.1)

                self.assertIsNotNone(meeting_payload)
                self.assertEqual(meeting_payload["meeting"]["status"], "completed")
                self.assertEqual(meeting_payload["derived_tasks"][0]["assignee"], "Alice")

                sync_request = urllib.request.Request(
                    f"{base_url}/api/demo/meeting/sync-feishu",
                    data=json.dumps(
                        {
                            "meeting_id": payload["meeting_id"],
                            "force": True,
                            "tasklist_id": "tasklist-guid",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                sync_payload = json.loads(urllib.request.urlopen(sync_request).read().decode("utf-8"))
                self.assertEqual(sync_payload["mode"], "dry_run")
                self.assertTrue(sync_payload["force"])
                self.assertEqual(sync_payload["tasklist_id"], "tasklist-guid")
                self.assertEqual(sync_payload["tasks"][0]["status"], "dry_run")

                decision_sync_request = urllib.request.Request(
                    f"{base_url}/api/demo/meeting/sync-decisions-base",
                    data=json.dumps({"meeting_id": payload["meeting_id"], "force": True}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                decision_sync_payload = json.loads(urllib.request.urlopen(decision_sync_request).read().decode("utf-8"))
                self.assertEqual(decision_sync_payload["mode"], "dry_run")
                self.assertEqual(decision_sync_payload["decisions"][0]["status"], "dry_run")
            finally:
                server.shutdown()
                server.server_close()
