# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import which
from unittest.mock import Mock, patch


LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from integrations import feishu_tasks
from integrations.feishu_tasks import DryRunTaskSink, LarkCliTaskSink, build_feishu_task_payload


class FeishuTaskSinkTests(unittest.TestCase):
    def test_dry_run_sink_returns_payload_without_external_write(self):
        task = {
            "id": 7,
            "title": "Ship review doc",
            "assignee": "Alice",
            "due_date": "2026-07-20",
            "source_evidence": "Alice: I will ship it.",
        }

        result = DryRunTaskSink().push_task(task)

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["provider"], "feishu")
        self.assertEqual(result["payload"]["summary"], "Ship review doc")
        self.assertIn("Alice", result["payload"]["description"])
        self.assertIsNone(result["external_id"])

    def test_lark_cli_sink_builds_command_and_extracts_task_identity(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "task": {
                            "guid": "task-guid",
                            "url": "https://example.feishu.cn/client/todo/task?guid=task-guid",
                        }
                    }
                }
            ),
            stderr="",
        )
        runner = Mock(return_value=completed)
        sink = LarkCliTaskSink(runner=runner, identity="user")
        task = {"id": 7, "title": "Ship review doc", "assignee": "Alice", "due_date": None, "source_evidence": "Evidence"}

        result = sink.push_task(task)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["external_id"], "task-guid")
        self.assertEqual(result["external_url"], "https://example.feishu.cn/client/todo/task?guid=task-guid")
        command = runner.call_args.args[0]
        self.assertIn(Path(command[0]).name, {"lark-cli", "lark-cli.cmd", "lark-cli.ps1"})
        self.assertEqual(command[1:4], ["task", "+create", "--as"])
        self.assertEqual(command[4], "user")
        self.assertIn("--summary", command)
        self.assertIn("--description", command)
        self.assertIn("--idempotency-key", command)
        self.assertEqual(command[command.index("--summary") + 1], "Ship review doc")

    def test_lark_cli_sink_returns_failed_result_when_cli_fails(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )
        sink = LarkCliTaskSink(runner=Mock(return_value=completed), identity="user")

        result = sink.push_task({"title": "Ship review doc"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("permission denied", result["error"])

    def test_lark_cli_sink_returns_failed_result_when_command_cannot_start(self):
        runner = Mock(side_effect=FileNotFoundError("lark-cli not found"))
        sink = LarkCliTaskSink(runner=runner, identity="user", command="missing-lark-cli")

        result = sink.push_task({"title": "Ship review doc"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("lark-cli not found", result["error"])

    def test_lark_cli_sink_uses_shortcut_due_and_idempotency_key(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"data": {"task": {"guid": "task-guid"}}}),
            stderr="",
        )
        runner = Mock(return_value=completed)
        sink = LarkCliTaskSink(runner=runner, identity="user", command="lark-cli")

        sink.push_task({"id": 42, "title": "Ship review doc", "due_date": "2026-07-20"})

        command = runner.call_args.args[0]
        self.assertEqual(command[command.index("--due") + 1], "2026-07-20")
        self.assertEqual(command[command.index("--idempotency-key") + 1], "minsight-derived-task-42")

    def test_lark_cli_sink_uses_resolved_assignee_and_tasklist(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"data": {"task": {"guid": "task-guid"}}}),
            stderr="",
        )
        resolver = Mock(return_value={"status": "resolved", "open_id": "ou_alice", "candidates": [], "error": None})
        runner = Mock(return_value=completed)
        sink = LarkCliTaskSink(
            runner=runner,
            identity="user",
            command="lark-cli",
            assignee_resolver=resolver,
            tasklist_id="https://applink.feishu.cn/client/todo/task_list?guid=list-guid",
        )

        result = sink.push_task({"id": 42, "title": "Ship review doc", "assignee": "Alice"})

        command = runner.call_args.args[0]
        self.assertEqual(command[command.index("--assignee") + 1], "ou_alice")
        self.assertEqual(command[command.index("--tasklist-id") + 1], "https://applink.feishu.cn/client/todo/task_list?guid=list-guid")
        self.assertEqual(result["assignee_open_id"], "ou_alice")
        self.assertEqual(result["assignee_resolution_status"], "resolved")

    def test_lark_cli_sink_records_unresolved_assignee_without_blocking_sync(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"data": {"task": {"guid": "task-guid"}}}),
            stderr="",
        )
        resolver = Mock(return_value={"status": "ambiguous", "open_id": None, "candidates": [{"name": "Alice"}], "error": None})
        runner = Mock(return_value=completed)
        sink = LarkCliTaskSink(runner=runner, identity="user", command="lark-cli", assignee_resolver=resolver)

        result = sink.push_task({"id": 42, "title": "Ship review doc", "assignee": "Alice"})

        command = runner.call_args.args[0]
        self.assertNotIn("--assignee", command)
        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["assignee_resolution_status"], "ambiguous")

    def test_lark_cli_command_prefers_windows_cmd_shim_when_available(self):
        with patch.object(feishu_tasks, "which") as fake_which:
            fake_which.side_effect = lambda name: "C:/npm/lark-cli.cmd" if name == "lark-cli.cmd" else None

            command = feishu_tasks.resolve_lark_cli_command()

        if os.name == "nt":
            self.assertEqual(command, "C:/npm/lark-cli.cmd")
        else:
            self.assertEqual(command, "lark-cli")

    def test_build_task_sink_reads_lab_env_when_process_env_is_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "MINSIGHT_FEISHU_SYNC_MODE=lark_cli\nMINSIGHT_FEISHU_IDENTITY=user\n",
                encoding="utf-8",
            )
            with patch.object(feishu_tasks, "_ENV_PATHS", [env_path]), patch.object(
                feishu_tasks, "_ENV_LOADED", False
            ), patch.dict(os.environ, {}, clear=True):
                sink = feishu_tasks.build_task_sink()

            self.assertIsInstance(sink, LarkCliTaskSink)
            self.assertEqual(sink.identity, "user")
            self.assertIsNone(sink.assignee_resolver)

    def test_build_task_sink_only_resolves_assignees_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "MINSIGHT_FEISHU_SYNC_MODE=lark_cli",
                        "MINSIGHT_FEISHU_IDENTITY=user",
                        "MINSIGHT_FEISHU_RESOLVE_ASSIGNEE=true",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.object(feishu_tasks, "_ENV_PATHS", [env_path]), patch.object(
                feishu_tasks, "_ENV_LOADED", False
            ), patch.dict(os.environ, {}, clear=True):
                sink = feishu_tasks.build_task_sink()

            self.assertIsInstance(sink, LarkCliTaskSink)
            self.assertIsNotNone(sink.assignee_resolver)


if __name__ == "__main__":
    unittest.main()
