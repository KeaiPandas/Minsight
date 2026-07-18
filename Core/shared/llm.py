# -*- coding: utf-8 -*-
"""LLM 客户端：只做“调用委派 + 路由日志”。

Core 已移除离线模拟链路，运行前必须在 .env 中配置至少一个可用 profile。
"""

from shared import config
from shared.backends.real import RealBackend


class LLMClient:
    def __init__(self):
        self._case = None
        self.call_log = []
        if not config.any_profile_configured():
            raise RuntimeError("no LLM profile configured in .env")
        self.backend = RealBackend()
        self.mode = "real (openai-compatible)"

    def set_case(self, case):
        """为后续扩展保留 case 上下文。"""
        self._case = case

    def complete(self, prompt, agent):
        model, profile = self.backend.resolve(agent)
        self.call_log.append({"agent": agent, "profile": profile, "model": model})
        return self.backend.complete(prompt, agent, self._case)
