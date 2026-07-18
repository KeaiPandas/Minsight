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

from integrations.feishu_contacts import LarkCliContactResolver


class FeishuContactResolverTests(unittest.TestCase):
    def test_resolves_unique_user_open_id(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"users": [{"open_id": "ou_alice", "name": "Alice"}]}),
            stderr="",
        )
        runner = Mock(return_value=completed)
        resolver = LarkCliContactResolver(runner=runner, identity="user", command="lark-cli")

        result = resolver.resolve("Alice")

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["open_id"], "ou_alice")
        command = runner.call_args.args[0]
        self.assertEqual(command[1:4], ["contact", "+search-user", "--as"])
        self.assertEqual(command[command.index("--query") + 1], "Alice")

    def test_returns_ambiguous_when_multiple_users_match(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "users": [
                            {"open_id": "ou_alice_1", "name": "Alice Zhang"},
                            {"open_id": "ou_alice_2", "name": "Alice Wang"},
                        ]
                    }
                }
            ),
            stderr="",
        )
        resolver = LarkCliContactResolver(runner=Mock(return_value=completed), identity="user", command="lark-cli")

        result = resolver.resolve("Alice")

        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertIsNone(result["open_id"])

    def test_returns_not_found_when_no_user_matches(self):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps({"users": []}), stderr="")
        resolver = LarkCliContactResolver(runner=Mock(return_value=completed), identity="user", command="lark-cli")

        result = resolver.resolve("Missing")

        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["open_id"])

    def test_returns_failed_when_cli_fails(self):
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="permission denied")
        resolver = LarkCliContactResolver(runner=Mock(return_value=completed), identity="user", command="lark-cli")

        result = resolver.resolve("Alice")

        self.assertEqual(result["status"], "failed")
        self.assertIn("permission denied", result["error"])


if __name__ == "__main__":
    unittest.main()
