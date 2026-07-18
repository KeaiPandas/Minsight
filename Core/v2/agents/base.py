# -*- coding: utf-8 -*-
"""Shared base classes for V2 agents."""

from shared.prompts import render


class BaseStructuredAgent:
    """Shared prompt rendering and LLM invocation."""

    name = ""
    output_model = None

    def __init__(self, repair_agent):
        self.repair_agent = repair_agent

    def _repair_fn(self, llm):
        return lambda raw, error: self.repair_agent.repair(llm, raw, error)

    def _complete(self, llm, **prompt_kwargs):
        return llm.complete(render("v2", self.name, **prompt_kwargs), agent=self.name)
