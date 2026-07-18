# -*- coding: utf-8 -*-
"""Extract key discussion points."""

from shared.models import KeyPointsOut, parse_as
from v2.agents.base import BaseStructuredAgent
from v2.agents.concurrency import map_segments


class KeyPointsAgent(BaseStructuredAgent):
    name = "key_points"
    output_model = KeyPointsOut

    def run(self, case, llm):
        raw = self._complete(llm, transcript=case["transcript"])
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        return out.key_points if ok else []

    def run_many(self, segments, llm):
        key_points = []
        seen = set()
        outputs = map_segments(lambda segment: self._run_segment(segment, llm), segments)
        for out, ok in outputs:
            if not ok:
                continue
            for item in out.key_points:
                key = _dedupe_key(item.topic, item.summary)
                if key in seen:
                    continue
                seen.add(key)
                key_points.append(item)
        return key_points

    def _run_segment(self, segment, llm):
        raw = self._complete(llm, transcript=segment["text"])
        return parse_as(self.output_model, raw, self._repair_fn(llm))


def _dedupe_key(*values):
    return "|".join(str(value or "").strip().lower() for value in values)
