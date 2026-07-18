# -*- coding: utf-8 -*-
"""Extract action items and decisions."""

from shared.models import ActionsDecisionsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class ActionsDecisionsAgent(BaseStructuredAgent):
    name = "actions_decisions"
    output_model = ActionsDecisionsOut

    def run(self, case, alias_map, llm):
        raw = self._complete(
            llm,
            transcript=case["transcript"],
            alias_map=alias_map,
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        if not ok:
            return [], []
        return out.action_items, out.decisions
