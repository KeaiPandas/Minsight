# -*- coding: utf-8 -*-
"""Central prompt template loader with project-level isolation."""

import os

_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
_cache = {}


def load_prompt(project, agent):
    """Read a prompt template for the given project and agent."""
    key = (project, agent)
    if key not in _cache:
        with open(os.path.join(_BASE, project, f"{agent}.txt"), encoding="utf-8") as f:
            _cache[key] = f.read()
    return _cache[key]


def render(project, agent, **kwargs):
    """Replace {{KEY}} placeholders with provided values."""
    text = load_prompt(project, agent)
    for key, val in kwargs.items():
        text = text.replace("{{" + key.upper() + "}}", str(val))
    return text
