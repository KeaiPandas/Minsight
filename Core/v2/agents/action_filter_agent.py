# -*- coding: utf-8 -*-
"""Filter segment-level action candidates into formal assigned tasks."""

import json

from shared.models import ActionItem, ActionItemsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class ActionFilterAgent(BaseStructuredAgent):
    name = "action_filter"
    output_model = ActionItemsOut

    def run(self, candidates, llm):
        if not candidates:
            return []
        if len(candidates) == 1:
            return [_coerce_action(candidates[0])]
        raw = self._complete(
            llm,
            candidates=json.dumps(_dump_items(candidates), ensure_ascii=False, indent=2),
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        return out.action_items if ok else [_coerce_action(item) for item in candidates]


def _dump_items(items):
    return [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in items
    ]


def _coerce_action(item):
    if isinstance(item, ActionItem):
        return item
    return ActionItem.model_validate(item)
