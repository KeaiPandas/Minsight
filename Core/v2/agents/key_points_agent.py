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
