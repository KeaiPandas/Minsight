# -*- coding: utf-8 -*-
"""Production LLM backend for OpenAI-compatible chat completion APIs."""

import os
import threading
import time

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
        max_retries, base_seconds = _retry_settings()
        attempt = 0
        while True:
            try:
                resp = self._client(profile).chat.completions.create(
                    model=profile["model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                if attempt >= max_retries or not _is_retryable(exc):
                    raise
                time.sleep(base_seconds * (2 ** attempt))
                attempt += 1


def _retry_settings():
    try:
        max_retries = int(os.getenv("MINSIGHT_LLM_MAX_RETRIES", "2"))
    except ValueError:
        max_retries = 2
    try:
        base_seconds = float(os.getenv("MINSIGHT_LLM_RETRY_BASE_SECONDS", "0.8"))
    except ValueError:
        base_seconds = 0.8
    return max(0, max_retries), max(0.0, base_seconds)


def _is_retryable(exc):
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    retry_markers = (
        "429",
        "rate limit",
        "ratelimit",
        "too many requests",
        "timeout",
        "temporarily unavailable",
        "connection reset",
    )
    return (
        "ratelimit" in name
        or "timeout" in name
        or any(marker in message for marker in retry_markers)
    )
