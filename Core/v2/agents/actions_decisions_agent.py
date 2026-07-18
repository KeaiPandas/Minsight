# -*- coding: utf-8 -*-
"""Extract action items and decisions."""

import json

from shared.meeting_info import build_roster_aliases, get_meeting_date, get_meeting_info
from shared.models import ActionsDecisionsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class ActionsDecisionsAgent(BaseStructuredAgent):
    name = "actions_decisions"
    output_model = ActionsDecisionsOut

    def run(self, case, alias_map, llm):
        authoritative_alias_map = {
            **(alias_map or {}),
            **build_roster_aliases(get_meeting_info(case)),
        }
        raw = self._complete(
            llm,
            transcript=case["transcript"],
            alias_map=json.dumps(authoritative_alias_map, ensure_ascii=False, indent=2),
            meeting_date=get_meeting_date(case),
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        if not ok:
            return [], []
        return out.action_items, out.decisions

    def run_many(self, case, segments, alias_map, llm):
        authoritative_alias_map = {
            **(alias_map or {}),
            **build_roster_aliases(get_meeting_info(case)),
        }
        actions = []
        decisions = []
        seen_actions = set()
        seen_decisions = set()
        for segment in segments:
            raw = self._complete(
                llm,
                transcript=segment["text"],
                alias_map=json.dumps(authoritative_alias_map, ensure_ascii=False, indent=2),
                meeting_date=get_meeting_date(case),
            )
            out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
            if not ok:
                continue
            for item in out.action_items:
                key = _action_key(item)
                if key in seen_actions:
                    continue
                seen_actions.add(key)
                actions.append(item)
            for item in out.decisions:
                key = _decision_key(item)
                if key in seen_decisions:
                    continue
                seen_decisions.add(key)
                decisions.append(item)
        return actions, decisions


def _action_key(item):
    return "|".join(
        _norm(value)
        for value in (item.task, item.owner, item.due)
    )


def _decision_key(item):
    return "|".join(
        _norm(value)
        for value in (item.decision, item.supersedes)
    )


def _norm(value):
    return str(value or "").strip().lower()
