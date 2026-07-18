# -*- coding: utf-8 -*-

import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from shared.backends.real import RealBackend


class RealBackendRetryTests(unittest.TestCase):
    def test_complete_retries_transient_rate_limit_errors(self):
        backend = RealBackend.__new__(RealBackend)
        backend._clients = {"strong": FakeOpenAIClient(failures=2)}
        backend._lock = threading.Lock()
        backend._profile_for = lambda _agent: (
            "strong",
            {
                "name": "strong",
                "model": "fake-model",
                "api_key": "fake-key",
                "base_url": None,
            },
        )

        with patch.dict(
            os.environ,
            {
                "MINSIGHT_LLM_MAX_RETRIES": "3",
                "MINSIGHT_LLM_RETRY_BASE_SECONDS": "0",
            },
        ):
            result = backend.complete("prompt", "actions_decisions")

        self.assertEqual(result, "ok")
        self.assertEqual(backend._clients["strong"].calls, 3)


class FakeOpenAIClient:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("Error code: 429 - rate limit")
        return FakeResponse("ok")


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeMessage:
    def __init__(self, content):
        self.content = content


if __name__ == "__main__":
    unittest.main()
