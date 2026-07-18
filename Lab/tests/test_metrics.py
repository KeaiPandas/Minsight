# -*- coding: utf-8 -*-

import unittest
from pathlib import Path
import sys


LAB_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from metrics import score_objective_dimensions
from helpers import load_fixture


class ObjectiveMetricsTests(unittest.TestCase):
    def test_participants_and_action_owners_are_scored_after_alias_normalization(self):
        fixture = load_fixture("objective_metrics_nickname.json")

        scores = score_objective_dimensions(fixture["case"], fixture["prediction"])

        self.assertEqual(scores["participants"], 1.0)
        self.assertEqual(scores["action_items"], 1.0)


if __name__ == "__main__":
    unittest.main()
