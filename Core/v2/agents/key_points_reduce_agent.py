# -*- coding: utf-8 -*-
"""Reduce segment-level key points into meeting-level topics."""

import json

from shared.models import KeyPoint, KeyPointsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class KeyPointsReduceAgent(BaseStructuredAgent):
    name = "key_points_reduce"
    output_model = KeyPointsOut

    def run(self, candidates, llm):
        if len(candidates) <= 6:
            return [_coerce_key_point(item) for item in candidates]
        raw = self._complete(
            llm,
            candidates=json.dumps(_dump_items(candidates), ensure_ascii=False, indent=2),
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        return out.key_points if ok else [_coerce_key_point(item) for item in candidates[:6]]


def _dump_items(items):
    return [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in items
    ]


def _coerce_key_point(item):
    if isinstance(item, KeyPoint):
        return item
    return KeyPoint.model_validate(item)
