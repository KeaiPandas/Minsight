# -*- coding: utf-8 -*-

import json
import sys
import threading
import time
import unittest
from pathlib import Path


CORE_ROOT = Path(__file__).resolve().parents[2] / "Core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from v2.agents.actions_decisions_agent import ActionsDecisionsAgent
from v2.agents.decision_filter_agent import DecisionFilterAgent
from v2.agents.key_points_agent import KeyPointsAgent
from v2.agents.key_points_reduce_agent import KeyPointsReduceAgent
from v2.agents.repair_agent import RepairAgent
from v2.agents.segment_agent import SegmentAgent
from v2.graph import extract_v2_graph


class FakeLLM:
    def __init__(self, responses):
        self.responses = {agent: list(values) for agent, values in responses.items()}
        self.prompts = []
        self.lock = threading.Lock()

    def complete(self, prompt, agent):
        with self.lock:
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
        prompt_texts = [call["prompt"] for call in llm.prompts]
        self.assertTrue(any("first chunk" in prompt for prompt in prompt_texts))
        self.assertTrue(any("second chunk" in prompt for prompt in prompt_texts))

    def test_key_points_agent_maps_segments_concurrently(self):
        llm = ConcurrentLLM("key_points")
        segments = [
            {"segment_id": f"seg_{idx:03d}", "text": f"chunk {idx}"}
            for idx in range(1, 5)
        ]

        key_points = KeyPointsAgent(RepairAgent()).run_many(segments, llm)

        self.assertEqual(len(key_points), 4)
        self.assertGreater(llm.max_active, 1)

    def test_key_points_reduce_agent_removes_off_topic_and_compresses_to_meeting_level_topics(self):
        llm = FakeLLM(
            {
                "key_points_reduce": [
                    json.dumps(
                        {
                            "key_points": [
                                {
                                    "topic": "Launch scope",
                                    "summary": "Launch moved to a limited gray release because QA risks remain.",
                                },
                                {
                                    "topic": "Operations reminder excluded",
                                    "summary": "The operations banner reminder is parked outside the current scope.",
                                },
                            ]
                        }
                    )
                ]
            }
        )
        candidates = [
            {"topic": "Launch date", "summary": "Launch date is discussed."},
            {"topic": "QA risk", "summary": "QA risk affects launch."},
            {"topic": "Resume review", "summary": "Off-topic job search chat."},
            {"topic": "Industry gossip", "summary": "Off-topic industry chat."},
            {"topic": "Implementation detail", "summary": "A local detail was debated."},
            {"topic": "Duplicate launch", "summary": "Launch date is repeated."},
            {"topic": "Another tangent", "summary": "Unrelated side discussion."},
        ]

        reduced = KeyPointsReduceAgent(RepairAgent()).run(candidates, llm)

        self.assertEqual(len(reduced), 2)
        self.assertEqual(reduced[0].topic, "Launch scope")
        self.assertEqual([call["agent"] for call in llm.prompts], ["key_points_reduce"])
        self.assertIn("Resume review", llm.prompts[0]["prompt"])

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
        prompt_texts = [call["prompt"] for call in llm.prompts]
        self.assertTrue(all("2026-07-18" in prompt for prompt in prompt_texts))
        self.assertTrue(all('"Alice": "Alice Chen"' in prompt for prompt in prompt_texts))
        self.assertTrue(any("Alice: I will send the launch brief today." in prompt for prompt in prompt_texts))
        self.assertTrue(all("full transcript should not be sent" not in prompt for prompt in prompt_texts))

    def test_actions_decisions_agent_maps_segments_concurrently(self):
        case = {
            "transcript": "full transcript",
            "meeting_info": {
                "date": "2026-07-18",
                "attendees": [{"account": "alice", "name": "Alice", "display_name": "Alice", "role": "PM"}],
            },
        }
        llm = ConcurrentLLM("actions_decisions")
        segments = [
            {"segment_id": f"seg_{idx:03d}", "text": f"Alice: action {idx}"}
            for idx in range(1, 5)
        ]

        actions, decisions = ActionsDecisionsAgent(RepairAgent()).run_many(case, segments, {}, llm)

        self.assertEqual(len(actions), 4)
        self.assertEqual(decisions, [])
        self.assertGreater(llm.max_active, 1)

    def test_decision_filter_agent_keeps_final_topic_decisions_and_drops_clarifications(self):
        llm = FakeLLM(
            {
                "decision_filter": [
                    json.dumps(
                        {
                            "decisions": [
                                {
                                    "decision": "Operations banner reminder is excluded from this release.",
                                    "supersedes": None,
                                    "evidence": "Owner: operations banner is not in this release.",
                                }
                            ]
                        }
                    )
                ]
            }
        )
        candidates = [
            {
                "decision": "28th is only the plan date, not launch.",
                "supersedes": None,
                "evidence": "PM: 28th is only the plan date, not launch.",
            },
            {
                "decision": "Permission request does not need approval flow redesign.",
                "supersedes": None,
                "evidence": "PM: no need to redo the approval flow.",
            },
            {
                "decision": "Operations banner reminder is excluded from this release.",
                "supersedes": None,
                "evidence": "Owner: operations banner is not in this release.",
            },
        ]

        filtered = DecisionFilterAgent(RepairAgent()).run(candidates, llm)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].decision, "Operations banner reminder is excluded from this release.")
        self.assertIn("28th is only the plan date", llm.prompts[0]["prompt"])
        self.assertIn("topic-level final decisions", llm.prompts[0]["prompt"])

    def test_graph_runs_reduce_and_filter_only_when_needed(self):
        case = {
            "id": "graph_01",
            "scenario": "graph",
            "transcript": "\n".join(f"Speaker: line {idx} discusses launch scope." for idx in range(220)),
            "meeting_info": {
                "date": "2026-07-18",
                "attendees": [
                    {"account": "alice", "name": "Alice", "display_name": "Alice", "role": "PM"}
                ],
            },
        }
        llm = FakeGraphLLM()

        result = extract_v2_graph(case, llm)

        agents = [call["agent"] for call in llm.prompts]
        self.assertIn("key_points_reduce", agents)
        self.assertIn("decision_filter", agents)
        self.assertLessEqual(len(result["key_points"]), 2)
        self.assertEqual(len(result["decisions"]), 1)

class FakeGraphLLM:
    def __init__(self):
        self.prompts = []
        self.call_log = []
        self.counts = {}

    def set_case(self, case):
        self.case = case

    def complete(self, prompt, agent):
        self.prompts.append({"agent": agent, "prompt": prompt})
        self.counts[agent] = self.counts.get(agent, 0) + 1
        if agent == "normalize":
            return json.dumps(
                {
                    "participants": [{"name": "Alice", "role": "PM"}],
                    "alias_map": {"Alice": "Alice"},
                }
            )
        if agent == "key_points":
            idx = self.counts[agent]
            return json.dumps(
                {
                    "key_points": [
                        {"topic": f"Launch scope {idx}", "summary": "Launch scope is discussed."},
                        {"topic": f"Side tangent {idx}", "summary": "Off-topic content."},
                    ]
                }
            )
        if agent == "actions_decisions":
            return json.dumps(
                {
                    "action_items": [
                        {
                            "task": "Send launch brief",
                            "owner": "Alice",
                            "due": None,
                            "evidence": "Speaker: line 1 discusses launch scope.",
                        }
                    ],
                    "decisions": [
                        {
                            "decision": "28th is a plan date, not launch.",
                            "supersedes": None,
                            "evidence": "Speaker: line 2 discusses launch scope.",
                        },
                        {
                            "decision": "Launch scope is limited.",
                            "supersedes": None,
                            "evidence": "Speaker: line 3 discusses launch scope.",
                        },
                    ],
                }
            )
        if agent == "key_points_reduce":
            return json.dumps(
                {
                    "key_points": [
                        {"topic": "Launch scope", "summary": "Launch scope is limited."}
                    ]
                }
            )
        if agent == "decision_filter":
            return json.dumps(
                {
                    "decisions": [
                        {
                            "decision": "Launch scope is limited.",
                            "supersedes": None,
                            "evidence": "Speaker: line 3 discusses launch scope.",
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected agent {agent}")


class ConcurrentLLM:
    def __init__(self, expected_agent):
        self.expected_agent = expected_agent
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.lock = threading.Lock()
        self.prompts = []

    def complete(self, prompt, agent):
        if agent != self.expected_agent:
            raise AssertionError(f"unexpected agent {agent}")
        with self.lock:
            self.calls += 1
            call_id = self.calls
            self.prompts.append({"agent": agent, "prompt": prompt})
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        if agent == "key_points":
            return json.dumps({"key_points": [{"topic": f"Topic {call_id}", "summary": f"Summary {call_id}"}]})
        return json.dumps(
            {
                "action_items": [
                    {
                        "task": f"Action {call_id}",
                        "owner": "Alice",
                        "due": None,
                        "evidence": "Alice: action",
                    }
                ],
                "decisions": [],
            }
        )


if __name__ == "__main__":
    unittest.main()
