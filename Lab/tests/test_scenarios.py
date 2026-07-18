# -*- coding: utf-8 -*-

import unittest
from pathlib import Path
import sys

CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from shared.dataio import load_cases


class ScenarioFixtureQualityTests(unittest.TestCase):
    def test_benchmark_cases_are_complex_enough_for_agent_iteration(self):
        cases = load_cases()

        self.assertGreaterEqual(len(cases), 6)
        for case in cases:
            with self.subTest(case_id=case["id"]):
                tags = set(case.get("complexity_tags", []))
                gold = case["gold"]

                self.assertGreaterEqual(len(case["transcript"]), 450)
                self.assertGreaterEqual(len(tags), 3)
                self.assertTrue(
                    {"mixed_topics", "distractors", "ambiguous_refs"} & tags,
                    "each case should include at least one confusion pattern",
                )
                self.assertGreaterEqual(len(gold.get("participants", [])), 3)
                self.assertGreaterEqual(len(gold.get("key_points", [])), 3)
                self.assertGreaterEqual(len(gold.get("action_items", [])), 2)
                self.assertGreaterEqual(len(gold.get("decisions", [])), 1)
                self.assertNotIn("alias_map", case)
                self.assertRegex(case.get("meeting_info", {}).get("date", ""), r"^\d{4}-\d{2}-\d{2}$")
                self.assertGreaterEqual(len(case.get("meeting_info", {}).get("attendees", [])), 3)


if __name__ == "__main__":
    unittest.main()
