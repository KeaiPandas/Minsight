# -*- coding: utf-8 -*-

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

DEPLOY_ROOT = Path(__file__).resolve().parents[1]
if str(DEPLOY_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(DEPLOY_ROOT.parent))

from Deploy.server import build_handler


class FakeWorkbenchRuntime:
    def __init__(self):
        self.created_meeting_id = "meeting-1"

    def list_demo_cases(self):
        return [
            {
                "case_id": "case-1",
                "scenario": "demo",
                "title": "case-1 demo",
                "transcript": "Alice: ship the summary.",
            }
        ]

    def list_meetings(self, limit=20):
        return [{"meeting_id": "meeting-1", "title": "Demo", "status": "completed", "created_at": "now"}]

    def resolve_case(self, scenario=None, case_id=None, transcript=None, title=None):
        return {
            "id": case_id or "adhoc",
            "scenario": scenario or "demo",
            "transcript": transcript or "Alice: ship the summary.",
            "title": title or "Demo",
        }

    def create_demo_meeting(self, title, transcript, scenario=None, source_case_id=None):
        return self.created_meeting_id

    def run_demo_existing(self, meeting_id, case):
        return self.get_demo_meeting_details(meeting_id)

    def get_demo_meeting_details(self, meeting_id):
        if meeting_id != self.created_meeting_id:
            return None
        return {
            "meeting": {"meeting_id": meeting_id, "title": "Demo", "status": "completed"},
            "minutes": {"title": "Demo", "summary_line": "1 action item assigned"},
            "derived_tasks": [],
            "decisions": [],
            "alerts": [],
        }

    def sync_demo_tasks_to_feishu(self, meeting_id, mode=None, force=False, tasklist_id=None):
        return {"meeting_id": meeting_id, "mode": mode or "dry_run", "force": force, "tasks": []}

    def sync_demo_decisions_to_feishu_base(self, meeting_id, mode=None, force=False):
        return {"meeting_id": meeting_id, "mode": mode or "dry_run", "force": force, "decisions": []}


class DeployServerTests(unittest.TestCase):
    def serve(self):
        runtime = FakeWorkbenchRuntime()
        with tempfile.TemporaryDirectory() as tmpdir:
            web_root = Path(tmpdir)
            (web_root / "index.html").write_text("<html><body>Minsight Workbench</body></html>", encoding="utf-8")
            handler = build_handler(runtime, web_root=web_root)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f"http://127.0.0.1:{server.server_address[1]}"
            finally:
                server.shutdown()
                server.server_close()

    def test_health_and_static_workbench_are_available(self):
        for base_url in self.serve():
            health = json.loads(urllib.request.urlopen(f"{base_url}/health").read().decode("utf-8"))
            self.assertEqual(health, {"status": "ok", "service": "minsight-deploy"})

            html = urllib.request.urlopen(f"{base_url}/").read().decode("utf-8")
            self.assertIn("Minsight Workbench", html)

    def test_benchmark_api_is_not_exposed(self):
        for base_url in self.serve():
            for path in ("/api/scenarios", "/api/runs", "/api/run"):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(f"{base_url}{path}")
                self.assertEqual(raised.exception.code, 404)

            request = urllib.request.Request(
                f"{base_url}/api/run",
                data=json.dumps({"scenario": "demo"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request)
            self.assertEqual(raised.exception.code, 404)

    def test_workbench_demo_api_is_exposed(self):
        for base_url in self.serve():
            cases = json.loads(urllib.request.urlopen(f"{base_url}/api/demo/cases").read().decode("utf-8"))
            self.assertEqual(cases["cases"][0]["case_id"], "case-1")

            request = urllib.request.Request(
                f"{base_url}/api/demo/run",
                data=json.dumps({"title": "Demo", "transcript": "Alice: ship the summary."}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            created = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
            self.assertEqual(created, {"meeting_id": "meeting-1", "status": "queued"})

            details = json.loads(
                urllib.request.urlopen(f"{base_url}/api/demo/meeting?id=meeting-1").read().decode("utf-8")
            )
            self.assertEqual(details["meeting"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
