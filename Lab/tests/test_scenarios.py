# -*- coding: utf-8 -*-

import unittest
from pathlib import Path
import sys

CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from shared.dataio import load_cases


class ScenarioFixtureQualityTests(unittest.TestCase):
    def test_annotation_rubric_documents_core_gold_boundaries(self):
        rubric = (Path(__file__).resolve().parents[2] / "docs" / "annotation_rubric.md").read_text(encoding="utf-8")

        for phrase in (
            "A decision is a topic-level conclusion",
            "A key point is a major discussion point",
            "An action item must have a concrete deliverable",
            "Evidence must be a verbatim transcript substring",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rubric)

    def test_benchmark_cases_are_complex_enough_for_agent_iteration(self):
        cases = load_cases()

        self.assertGreaterEqual(len(cases), 7)
        self.assertIn("real_01", {case["id"] for case in cases})
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
                expected_min_participants = 2 if "real_transcript" in tags else 3
                self.assertGreaterEqual(
                    len(gold.get("participants", [])),
                    expected_min_participants,
                )
                self.assertGreaterEqual(len(gold.get("key_points", [])), 3)
                self.assertGreaterEqual(len(gold.get("action_items", [])), 2)
                self.assertGreaterEqual(len(gold.get("decisions", [])), 1)
                self.assertNotIn("alias_map", case)
                self.assertRegex(case.get("meeting_info", {}).get("date", ""), r"^\d{4}-\d{2}-\d{2}$")
                self.assertGreaterEqual(
                    len(case.get("meeting_info", {}).get("attendees", [])),
                    expected_min_participants,
                )

    def test_gold_action_and_decision_evidence_is_verbatim_transcript_text(self):
        for case in load_cases():
            transcript = case["transcript"]
            for section in ("action_items", "decisions"):
                for item in case["gold"].get(section, []):
                    with self.subTest(case_id=case["id"], section=section, evidence=item.get("evidence")):
                        evidence = item.get("evidence", "")

                        self.assertTrue(evidence)
                        self.assertIn(evidence, transcript)

    def test_decision_rubric_keeps_topic_level_exclusions_but_not_inline_clarifications(self):
        cases = {case["id"]: case for case in load_cases()}
        nick_decisions = " ".join(
            item["decision"] for item in cases["nick_01"]["gold"].get("decisions", [])
        )
        real_decisions = " ".join(
            item["decision"] for item in cases["real_01"]["gold"].get("decisions", [])
        )

        self.assertNotIn("录屏", nick_decisions)
        self.assertNotIn("发票", nick_decisions)
        self.assertNotIn("问卷", nick_decisions)
        self.assertIn("暂缓", real_decisions)
        self.assertIn("优先级", real_decisions)


if __name__ == "__main__":
    unittest.main()
