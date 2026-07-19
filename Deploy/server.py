# -*- coding: utf-8 -*-
"""Production-facing Minsight workbench HTTP entrypoint.

This module intentionally exposes only the business workbench APIs. Benchmark
evaluation stays in Lab and should not be mounted by deployable services.
"""

import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEPLOY_ROOT = Path(__file__).resolve().parent
WEB_ROOT = DEPLOY_ROOT / "web"

try:
    from .runtime import WorkbenchRuntime
except ImportError:  # pragma: no cover - script execution path
    from runtime import WorkbenchRuntime


MEETING_THREADS = {}


def build_handler(runtime, web_root=None):
    static_root = str(web_root or WEB_ROOT)

    class WorkbenchHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=static_root, **kwargs)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                return self._send_json({"status": "ok", "service": "minsight-deploy"})
            if parsed.path == "/api/demo/cases":
                return self._send_json({"cases": runtime.list_demo_cases()})
            if parsed.path == "/api/demo/meetings":
                return self._send_json({"meetings": runtime.list_meetings()})
            if parsed.path == "/api/demo/meeting":
                meeting_id = parse_qs(parsed.query).get("id", [None])[0]
                if not meeting_id:
                    return self._send_json({"error": "missing meeting id"}, status=HTTPStatus.BAD_REQUEST)
                details = runtime.get_demo_meeting_details(meeting_id)
                if not details:
                    return self._send_json({"error": "meeting not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json(details)
            if self._is_benchmark_path(parsed.path):
                return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            try:
                if parsed.path == "/api/demo/run":
                    meeting_id = self._start_background_meeting(
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
                        force=bool(payload.get("force")),
                        tasklist_id=(payload.get("tasklist_id") or "").strip() or None,
                    )
                    return self._send_json(result)
                if parsed.path == "/api/demo/meeting/sync-decisions-base":
                    meeting_id = payload.get("meeting_id")
                    if not meeting_id:
                        return self._send_json({"error": "missing meeting id"}, status=HTTPStatus.BAD_REQUEST)
                    result = runtime.sync_demo_decisions_to_feishu_base(
                        meeting_id,
                        mode=payload.get("mode") or None,
                        force=bool(payload.get("force")),
                    )
                    return self._send_json(result)
                return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            except Exception as exc:
                return self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_DELETE(self):
            return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        @staticmethod
        def _is_benchmark_path(path):
            return path in {"/api/scenarios", "/api/runs", "/api/run"}

        def _start_background_meeting(self, title, scenario, case_id, transcript):
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
            MEETING_THREADS[meeting_id] = thread
            thread.start()
            return meeting_id

        def _send_json(self, data, status=HTTPStatus.OK):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return WorkbenchHandler


def main():
    host = os.getenv("MINSIGHT_HOST", "127.0.0.1")
    port = int(os.getenv("MINSIGHT_PORT", "8788"))
    db_path = os.getenv("MINSIGHT_DB_PATH") or str(DEPLOY_ROOT / "minsight_deploy.sqlite")
    runtime = WorkbenchRuntime(db_path=db_path)
    recovered = runtime.recover_interrupted_meetings()
    if recovered:
        print(f"[minsight-deploy] marked {len(recovered)} interrupted meeting(s) as failed")
    server = ThreadingHTTPServer((host, port), build_handler(runtime))
    print(f"[minsight-deploy] http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
