# -*- coding: utf-8 -*-
"""Lab web console and HTTP API."""

import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from runtime import BenchmarkRuntime

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_ROOT = os.path.join(ROOT, "web")
RUN_THREADS = {}
DEMO_THREADS = {}


def build_handler(runtime):
    class BenchmarkHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=WEB_ROOT, **kwargs)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/scenarios":
                return self._send_json({"scenarios": runtime.list_scenarios()})
            if parsed.path == "/api/demo/cases":
                return self._send_json({"cases": runtime.list_demo_cases()})
            if parsed.path == "/api/runs":
                return self._send_json({"runs": runtime.list_runs()})
            if parsed.path == "/api/demo/meetings":
                return self._send_json({"meetings": runtime.list_meetings()})
            if parsed.path == "/api/run":
                run_id = parse_qs(parsed.query).get("id", [None])[0]
                if not run_id:
                    return self._send_json({"error": "missing run id"}, status=HTTPStatus.BAD_REQUEST)
                details = runtime.get_run_details(run_id)
                if not details:
                    return self._send_json({"error": "run not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json(details)
            if parsed.path == "/api/demo/meeting":
                meeting_id = parse_qs(parsed.query).get("id", [None])[0]
                if not meeting_id:
                    return self._send_json({"error": "missing meeting id"}, status=HTTPStatus.BAD_REQUEST)
                details = runtime.get_demo_meeting_details(meeting_id)
                if not details:
                    return self._send_json({"error": "meeting not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json(details)
            return super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            try:
                if parsed.path == "/api/run":
                    run_id = self._start_background_run(
                        scenario=payload.get("scenario") or None,
                        plain=bool(payload.get("plain")),
                    )
                    return self._send_json({"run_id": run_id, "status": "queued"}, status=HTTPStatus.ACCEPTED)
                if parsed.path == "/api/demo/run":
                    meeting_id = self._start_background_demo(
                        title=(payload.get("title") or "").strip() or None,
                        scenario=payload.get("scenario") or None,
                        case_id=payload.get("case_id") or None,
                        transcript=(payload.get("transcript") or "").strip() or None,
                    )
                    return self._send_json({"meeting_id": meeting_id, "status": "queued"}, status=HTTPStatus.ACCEPTED)
                if parsed.path == "/api/demo/meeting/sync-feishu":
                    meeting_id = payload.get("meeting_id")
                    if not meeting_id:
                        return self._send_json({"error": "missing meeting id"}, status=HTTPStatus.BAD_REQUEST)
                    result = runtime.sync_demo_tasks_to_feishu(
                        meeting_id,
                        mode=payload.get("mode") or None,
                    )
                    return self._send_json(result)
                return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            except Exception as exc:
                return self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_DELETE(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/run":
                return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            run_id = parse_qs(parsed.query).get("id", [None])[0]
            if not run_id:
                return self._send_json({"error": "missing run id"}, status=HTTPStatus.BAD_REQUEST)
            deleted = runtime.delete_run(run_id)
            if not deleted:
                return self._send_json({"error": "run not found"}, status=HTTPStatus.NOT_FOUND)
            thread = RUN_THREADS.pop(run_id, None)
            if thread and thread.is_alive():
                pass
            return self._send_json({"run_id": run_id, "deleted": True})

        def _start_background_run(self, scenario, plain):
            run_id = runtime.create_run(scenario=scenario, plain=plain)

            def _job():
                runtime.run_benchmark_existing(run_id=run_id, scenario=scenario, plain=plain)

            thread = threading.Thread(target=_job, daemon=True)
            RUN_THREADS[run_id] = thread
            thread.start()
            return run_id

        def _start_background_demo(self, title, scenario, case_id, transcript):
            case = runtime.resolve_case(scenario=scenario, case_id=case_id, transcript=transcript, title=title)
            meeting_id = runtime.create_demo_meeting(
                title=title or case.get("title") or case["id"],
                transcript=case["transcript"],
                scenario=case.get("scenario"),
                source_case_id=case["id"] if case_id else None,
            )

            def _job():
                runtime.run_demo_existing(meeting_id=meeting_id, case=case)

            thread = threading.Thread(target=_job, daemon=True)
            DEMO_THREADS[meeting_id] = thread
            thread.start()
            return meeting_id

        def _send_json(self, data, status=HTTPStatus.OK):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return BenchmarkHandler


def main():
    port = 8787
    runtime = BenchmarkRuntime()
    server = ThreadingHTTPServer(("127.0.0.1", port), build_handler(runtime))
    print(f"[lab-ui] http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
