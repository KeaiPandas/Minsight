# -*- coding: utf-8 -*-
"""Extract key discussion points."""

from shared.models import KeyPointsOut, parse_as
from v2.agents.base import BaseStructuredAgent


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
        for segment in segments:
            raw = self._complete(llm, transcript=segment["text"])
            out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
            if not ok:
                continue
            for item in out.key_points:
                key = _dedupe_key(item.topic, item.summary)
                if key in seen:
                    continue
                seen.add(key)
                key_points.append(item)
        return key_points


def _dedupe_key(*values):
    return "|".join(str(value or "").strip().lower() for value in values)
