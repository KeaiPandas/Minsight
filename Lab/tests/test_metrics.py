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

    def test_action_items_penalize_extra_items_and_explain_matches(self):
        fixture = load_fixture("objective_metrics_w15.json")

        objective = score_objective_dimensions(
            fixture["case"],
            fixture["prediction_with_extra_and_bad_evidence"],
        )

        self.assertLess(objective["scores"]["action_items"], 1.0)
        self.assertGreater(objective["scores"]["action_items"], 0.4)
        action_details = objective["details"]["action_items"]
        self.assertEqual(action_details["gold_count"], 2)
        self.assertEqual(action_details["predicted_count"], 3)
        self.assertEqual(action_details["extra_items"], 1)
        self.assertEqual(len(action_details["matches"]), 2)
        self.assertTrue(all("task_similarity" in match for match in action_details["matches"]))

    def test_format_and_evidence_details_are_deterministic(self):
        fixture = load_fixture("objective_metrics_w15.json")

        objective = score_objective_dimensions(
            fixture["case"],
            fixture["prediction_with_extra_and_bad_evidence"],
        )

        self.assertLess(objective["scores"]["format_valid"], 1.0)
        self.assertLess(objective["scores"]["evidence"], 1.0)
        self.assertEqual(
            objective["details"]["format_valid"]["invalid_due_values"],
            ["next Monday", "2026/07/19"],
        )
        self.assertEqual(objective["details"]["format_valid"]["empty_action_owners"], 1)
        self.assertEqual(objective["details"]["evidence"]["checked"], 4)
        self.assertEqual(objective["details"]["evidence"]["matched"], 2)

    def test_evidence_allows_non_verbatim_keyword_overlap(self):
        case = {
            "transcript": (
                "Alice: Please send the customer whitelist to Bob by Friday. "
                "Carol: We decided not to record this meeting."
            ),
            "gold": {
                "action_items": [
                    {
                        "task": "Send customer whitelist to Bob",
                        "owner": "Alice",
                        "due": None,
                        "evidence": "Alice asked to send the customer whitelist to Bob.",
                    }
                ],
                "decisions": [
                    {
                        "decision": "Do not record this meeting",
                        "evidence": "Carol decided not to record this meeting.",
                    }
                ],
            },
        }
        prediction = {
            "participants": [],
            "key_points": [],
            "action_items": [
                {
                    "task": "Send customer whitelist to Bob",
                    "owner": "Alice",
                    "due": None,
                    "evidence": "customer whitelist to Bob by Friday",
                },
                {
                    "task": "Prepare invoice",
                    "owner": "Mallory",
                    "due": None,
                    "evidence": "invoice approval was confirmed",
                },
            ],
            "decisions": [
                {
                    "decision": "Do not record the meeting",
                    "evidence": "recording should be skipped for the meeting",
                }
            ],
        }

        objective = score_objective_dimensions(case, prediction)

        self.assertEqual(objective["details"]["evidence"]["checked"], 3)
        self.assertEqual(objective["details"]["evidence"]["matched"], 2)
        self.assertAlmostEqual(objective["scores"]["evidence"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
