# -*- coding: utf-8 -*-

import json
import sys
import unittest
from pathlib import Path


CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from v2.agents.actions_decisions_agent import ActionsDecisionsAgent
from v2.agents.key_points_agent import KeyPointsAgent
from v2.agents.repair_agent import RepairAgent
from v2.agents.segment_agent import SegmentAgent


class FakeLLM:
    def __init__(self, responses):
        self.responses = {agent: list(values) for agent, values in responses.items()}
        self.prompts = []

    def complete(self, prompt, agent):
        self.prompts.append({"agent": agent, "prompt": prompt})
        values = self.responses.setdefault(agent, [])
        if not values:
            raise AssertionError(f"unexpected call for {agent}")
        return values.pop(0)


class V2WorkflowHardeningTests(unittest.TestCase):
    def test_segment_agent_short_circuits_short_transcripts(self):
        case = {"transcript": "Alice: short meeting.\nBob: one decision."}

        segments = SegmentAgent(max_chars=200).run(case)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["segment_id"], "seg_001")
        self.assertEqual(segments[0]["text"], case["transcript"])

    def test_segment_agent_splits_long_transcripts_into_ordered_windows(self):
        case = {
            "transcript": "\n".join(
                [
                    "Alice: topic A needs a launch decision.",
                    "Bob: action for topic A.",
                    "Carol: topic B changes priority.",
                    "Dave: action for topic B.",
                ]
            )
        }

        segments = SegmentAgent(max_chars=70, overlap_lines=1).run(case)

        self.assertGreater(len(segments), 1)
        self.assertEqual([item["segment_id"] for item in segments], ["seg_001", "seg_002", "seg_003"])
        self.assertIn("Bob: action for topic A.", segments[1]["text"])

    def test_key_points_agent_maps_segments_and_reduces_duplicate_topics(self):
        llm = FakeLLM(
            {
                "key_points": [
                    json.dumps(
                        {
                            "key_points": [
                                {"topic": "Launch", "summary": "Launch is delayed."}
                            ]
                        }
                    ),
                    json.dumps(
                        {
                            "key_points": [
                                {"topic": "Launch", "summary": "Launch is delayed."},
                                {"topic": "Risk", "summary": "QA risk remains."},
                            ]
                        }
                    ),
                ]
            }
        )
        agent = KeyPointsAgent(RepairAgent())
        segments = [
            {"segment_id": "seg_001", "text": "first chunk"},
            {"segment_id": "seg_002", "text": "second chunk"},
        ]

        key_points = agent.run_many(segments, llm)

        self.assertEqual(len(key_points), 2)
        self.assertEqual([item.topic for item in key_points], ["Launch", "Risk"])
        self.assertEqual([call["agent"] for call in llm.prompts], ["key_points", "key_points"])
        self.assertIn("first chunk", llm.prompts[0]["prompt"])
        self.assertIn("second chunk", llm.prompts[1]["prompt"])

    def test_actions_decisions_agent_maps_segments_with_roster_and_date_then_reduces_duplicates(self):
        case = {
            "transcript": "full transcript should not be sent when segments exist",
            "meeting_info": {
                "date": "2026-07-18",
                "attendees": [
                    {
                        "account": "alice",
                        "name": "Alice Chen",
                        "display_name": "Alice",
                        "role": "PM",
                    }
                ],
            },
        }
        llm = FakeLLM(
            {
                "actions_decisions": [
                    json.dumps(
                        {
                            "action_items": [
                                {
                                    "task": "Send launch brief",
                                    "owner": "Alice",
                                    "due": "2026-07-18",
                                    "evidence": "Alice: I will send the launch brief today.",
                                }
                            ],
                            "decisions": [
                                {
                                    "decision": "Delay launch",
                                    "supersedes": None,
                                    "evidence": "Delay launch.",
                                }
                            ],
                        }
                    ),
                    json.dumps(
                        {
                            "action_items": [
                                {
                                    "task": "Send launch brief",
                                    "owner": "Alice",
                                    "due": "2026-07-18",
                                    "evidence": "Alice: I will send the launch brief today.",
                                }
                            ],
                            "decisions": [
                                {
                                    "decision": "Delay launch",
                                    "supersedes": None,
                                    "evidence": "Delay launch.",
                                }
                            ],
                        }
                    ),
                ]
            }
        )
        agent = ActionsDecisionsAgent(RepairAgent())
        segments = [
            {"segment_id": "seg_001", "text": "Alice: I will send the launch brief today."},
            {"segment_id": "seg_002", "text": "Decision: Delay launch."},
        ]

        actions, decisions = agent.run_many(case, segments, {"Alice": "Alice Chen"}, llm)

        self.assertEqual(len(actions), 1)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("2026-07-18", llm.prompts[0]["prompt"])
        self.assertIn('"Alice": "Alice Chen"', llm.prompts[0]["prompt"])
        self.assertIn("Alice: I will send the launch brief today.", llm.prompts[0]["prompt"])
        self.assertNotIn("full transcript should not be sent", llm.prompts[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
