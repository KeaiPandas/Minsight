# -*- coding: utf-8 -*-
"""真实后端（可上线）：任意 OpenAI 兼容接口。

本文件只含生产逻辑，不含任何模拟/失败变换。模型与路由全部来自 .env：
每个 profile 一套 base_url/api_key/model，每个 agent 路由到一个 profile。
"""

from shared import config
from shared.backends.base import Backend


class RealBackend(Backend):
    def __init__(self):
        self._profiles = config.configured_profiles()
        if not self._profiles:
            raise RuntimeError("no LLM profile configured in .env")
        self._clients = {}

    def _profile_for(self, agent):
        name = config.agent_profile_name(agent)
        profile = self._profiles.get(name)
        if profile is None:                        # 该 agent 的 profile 未配置则回落任意已配置项
            name, profile = next(iter(self._profiles.items()))
        return name, profile

    def resolve(self, agent):
        _, profile = self._profile_for(agent)
        return profile["model"], profile["name"]

    def _client(self, profile):
        from openai import OpenAI                   # 延迟导入，仅真实模式需要
        key = profile["name"]
        if key not in self._clients:
            if profile["base_url"]:
                self._clients[key] = OpenAI(api_key=profile["api_key"],
                                            base_url=profile["base_url"])
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
