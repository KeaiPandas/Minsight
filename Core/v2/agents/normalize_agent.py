# -*- coding: utf-8 -*-
"""Normalize speaker and alias information."""

from shared.meeting_info import build_roster_aliases, get_meeting_info, render_meeting_info
from shared.models import ParticipantsOut, parse_as
from v2.agents.base import BaseStructuredAgent


class NormalizeAgent(BaseStructuredAgent):
    name = "normalize"
    output_model = ParticipantsOut

    def run(self, case, llm):
        raw = self._complete(
            llm,
            transcript=case["transcript"],
            meeting_info=render_meeting_info(case),
        )
        out, ok = parse_as(self.output_model, raw, self._repair_fn(llm))
        if not ok:
            return [], {}
        authoritative = build_roster_aliases(get_meeting_info(case))
        merged_alias_map = {**out.alias_map, **authoritative}
        for participant in out.participants:
            participant.name = merged_alias_map.get(participant.name, participant.name)
        return out.participants, merged_alias_map
