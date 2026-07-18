# -*- coding: utf-8 -*-
"""Repair agent for schema correction."""

from shared.prompts import render


class RepairAgent:
    name = "repair"

    def repair(self, llm, raw, error):
        return llm.complete(
            render("v2", self.name, raw=raw, error=error),
            agent=self.name,
        )
