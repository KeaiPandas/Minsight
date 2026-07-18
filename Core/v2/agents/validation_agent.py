# -*- coding: utf-8 -*-
"""Merge and validate structured extraction output."""


class ValidationAgent:
    name = "validate"

    def run(self, participants, key_points, action_items, decisions, alias_map):
        parts = [p.model_dump() for p in participants]
        kps = [k.model_dump() for k in key_points]
        acts = []
        for action in action_items:
            item = action.model_dump()
            item["owner"] = alias_map.get(item["owner"], item["owner"])
            acts.append(item)
        decs = [d.model_dump() for d in decisions]
        return {
            "participants": parts,
            "key_points": kps,
            "action_items": acts,
            "decisions": decs,
            "_format_valid": True,
        }
