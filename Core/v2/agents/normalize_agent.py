# -*- coding: utf-8 -*-
"""Normalize speaker and alias information."""

from shared.models import ParticipantsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class NormalizeAgent(BaseStructuredAgent):
    name = "normalize"
    output_model = ParticipantsOut

    def run(self, case, llm):
        raw = self._complete(llm, transcript=case["transcript"])
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        if not ok:
            return [], {}
        return out.participants, out.alias_map
