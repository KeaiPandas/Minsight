# -*- coding: utf-8 -*-
"""V2 LangGraph workflow built from explicit agents."""

from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from v2.agents.action_filter_agent import ActionFilterAgent
from v2.agents.actions_decisions_agent import ActionsDecisionsAgent
from v2.agents.decision_filter_agent import DecisionFilterAgent
from v2.agents.key_points_agent import KeyPointsAgent
from v2.agents.key_points_reduce_agent import KeyPointsReduceAgent
from v2.agents.normalize_agent import NormalizeAgent
from v2.agents.repair_agent import RepairAgent
from v2.agents.segment_agent import SegmentAgent
from v2.agents.validation_agent import ValidationAgent


class S(TypedDict, total=False):
    case: Any
    segments: List[Dict]
    participants: List
    alias_map: Dict
    key_points: List
    action_items: List
    decisions: List
    result: Dict


def build_app(llm):
    repair_agent = RepairAgent()
    segment_agent = SegmentAgent()
    normalize_agent = NormalizeAgent(repair_agent)
    key_points_agent = KeyPointsAgent(repair_agent)
    key_points_reduce_agent = KeyPointsReduceAgent(repair_agent)
    actions_decisions_agent = ActionsDecisionsAgent(repair_agent)
    action_filter_agent = ActionFilterAgent(repair_agent)
    decision_filter_agent = DecisionFilterAgent(repair_agent)
    validation_agent = ValidationAgent()

    def n_segment(state: S):
        return {"segments": segment_agent.run(state["case"])}

    def n_normalize(state: S):
        participants, alias_map = normalize_agent.run(state["case"], llm)
        return {"participants": participants, "alias_map": alias_map}

    def n_keypoints(state: S):
        segments = state.get("segments") or [{"text": state["case"]["transcript"]}]
        return {"key_points": key_points_agent.run_many(segments, llm)}

    def n_keypoints_reduce(state: S):
        return {"key_points": key_points_reduce_agent.run(state.get("key_points", []), llm)}

    def n_actions(state: S):
        segments = state.get("segments") or [{"text": state["case"]["transcript"]}]
        if len(segments) == 1 and segments[0].get("text") == state["case"]["transcript"]:
            action_items, decisions = actions_decisions_agent.run(
                state["case"],
                state.get("alias_map", {}),
                llm,
            )
        else:
            action_items, decisions = actions_decisions_agent.run_many(
                state["case"],
                segments,
                state.get("alias_map", {}),
                llm,
            )
        return {"action_items": action_items, "decisions": decisions}

    def n_action_filter(state: S):
        return {"action_items": action_filter_agent.run(state.get("action_items", []), llm)}

    def n_decision_filter(state: S):
        return {"decisions": decision_filter_agent.run(state.get("decisions", []), llm)}

    def n_validate(state: S):
        return {
            "result": validation_agent.run(
                state.get("participants", []),
                state.get("key_points", []),
                state.get("action_items", []),
                state.get("decisions", []),
                state.get("alias_map", {}),
            )
        }

    g = StateGraph(S)
    g.add_node("segment", n_segment)
    g.add_node("normalize", n_normalize)
    g.add_node("key_points", n_keypoints)
    g.add_node("key_points_reduce", n_keypoints_reduce)
    g.add_node("actions", n_actions)
    g.add_node("action_filter", n_action_filter)
    g.add_node("decision_filter", n_decision_filter)
    g.add_node("validate", n_validate)
    g.set_entry_point("segment")
    g.add_edge("segment", "normalize")
    g.add_edge("normalize", "key_points")
    g.add_edge("normalize", "actions")
    g.add_edge("key_points", "key_points_reduce")
    g.add_edge("actions", "action_filter")
    g.add_edge("actions", "decision_filter")
    g.add_edge("key_points_reduce", "validate")
    g.add_edge("action_filter", "validate")
    g.add_edge("decision_filter", "validate")
    g.add_edge("validate", END)
    return g.compile()


def extract_v2_graph(case, llm):
    llm.set_case(case)
    app = build_app(llm)
    out = app.invoke({"case": case})
    return out["result"]
