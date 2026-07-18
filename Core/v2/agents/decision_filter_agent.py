# -*- coding: utf-8 -*-
"""Filter candidate decisions down to final topic-level decisions."""

import json

from shared.models import Decision, DecisionsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class DecisionFilterAgent(BaseStructuredAgent):
    name = "decision_filter"
    output_model = DecisionsOut

    def run(self, candidates, llm):
        if not candidates:
            return []
        if len(candidates) == 1:
            return [_coerce_decision(candidates[0])]
        raw = self._complete(
            llm,
            candidates=json.dumps(_dump_items(candidates), ensure_ascii=False, indent=2),
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        return out.decisions if ok else [_coerce_decision(item) for item in candidates]


def _dump_items(items):
    return [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in items
    ]


def _coerce_decision(item):
    if isinstance(item, Decision):
        return item
    return Decision.model_validate(item)
