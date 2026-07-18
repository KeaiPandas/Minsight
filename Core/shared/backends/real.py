# -*- coding: utf-8 -*-
"""Production LLM backend for OpenAI-compatible chat completion APIs."""

import threading

from shared import config
from shared.backends.base import Backend


class RealBackend(Backend):
    def __init__(self):
        self._profiles = config.configured_profiles()
        if not self._profiles:
            raise RuntimeError("no LLM profile configured in .env")
        self._clients = {}
        self._lock = threading.Lock()

    def _profile_for(self, agent):
        name = config.agent_profile_name(agent)
        profile = self._profiles.get(name)
        if profile is None:
            name, profile = next(iter(self._profiles.items()))
        return name, profile

    def resolve(self, agent):
        _, profile = self._profile_for(agent)
        return profile["model"], profile["name"]

    def _client(self, profile):
        from openai import OpenAI

        key = profile["name"]
        with self._lock:
            if key not in self._clients:
                if profile["base_url"]:
                    self._clients[key] = OpenAI(
                        api_key=profile["api_key"],
                        base_url=profile["base_url"],
                    )
                else:
                    self._clients[key] = OpenAI(api_key=profile["api_key"])
            return self._clients[key]

    def complete(self, prompt, agent, case=None):
        _, profile = self._profile_for(agent)
        resp = self._client(profile).chat.completions.create(
            model=profile["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content
