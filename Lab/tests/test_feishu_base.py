# -*- coding: utf-8 -*-

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from integrations.feishu_base import DryRunDecisionSink, LarkCliBaseDecisionSink, build_decision_payload


class FeishuBaseDecisionSinkTests(unittest.TestCase):
    def test_dry_run_returns_payload_without_external_write(self):
        meeting = {"meeting_id": "meeting-1", "title": "Weekly", "scenario": "demo"}
        decision = {"id": 3, "decision": "Delay launch", "supersedes": "Launch Friday", "evidence": "Delay it."}

        result = DryRunDecisionSink().push_decision(meeting, decision)

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["payload"]["Decision"], "Delay launch")
        self.assertEqual(result["external_id"], None)

    def test_lark_cli_base_sink_builds_record_upsert_command(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"record": {"record_id": "rec_123", "record_url": "https://example.feishu.cn/base/rec_123"}}),
            stderr="",
        )
        runner = Mock(return_value=completed)
        sink = LarkCliBaseDecisionSink(
            runner=runner,
            identity="user",
            command="lark-cli",
            base_token="app_base",
            table_id="tbl_decisions",
        )
        meeting = {"meeting_id": "meeting-1", "title": "Weekly", "scenario": "demo"}
        decision = {"id": 3, "decision": "Delay launch", "supersedes": "Launch Friday", "evidence": "Delay it."}

        result = sink.push_decision(meeting, decision)

        command = runner.call_args.args[0]
        self.assertEqual(command[1:4], ["base", "+record-upsert", "--as"])
        self.assertEqual(command[command.index("--base-token") + 1], "app_base")
        self.assertEqual(command[command.index("--table-id") + 1], "tbl_decisions")
        payload = json.loads(command[command.index("--json") + 1])
        self.assertEqual(payload["Decision"], "Delay launch")
        self.assertEqual(payload["Decision ID"], "meeting-1:3")
        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["external_id"], "rec_123")

    def test_lark_cli_base_sink_reports_missing_configuration(self):
        sink = LarkCliBaseDecisionSink(runner=Mock(), identity="user", command="lark-cli", base_token=None, table_id=None)

        result = sink.push_decision({"meeting_id": "meeting-1"}, {"id": 3, "decision": "Delay launch"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("MINSIGHT_FEISHU_BASE_TOKEN", result["error"])

    def test_build_decision_payload_includes_traceability_fields(self):
        payload = build_decision_payload(
            {"meeting_id": "meeting-1", "title": "Weekly", "scenario": "demo"},
            {"id": 3, "decision": "Delay launch", "supersedes": "Launch Friday", "evidence": "Delay it."},
        )

        self.assertEqual(payload["Meeting ID"], "meeting-1")
        self.assertEqual(payload["Decision"], "Delay launch")
        self.assertEqual(payload["Evidence"], "Delay it.")


if __name__ == "__main__":
    unittest.main()
