# -*- coding: utf-8 -*-
"""后端统一接口：当前仅保留真实后端实现。"""


class Backend:
    def resolve(self, agent):
        """返回 (model_name, profile_name)，仅用于调用日志/路由展示。"""
        raise NotImplementedError

    def complete(self, prompt, agent, case=None):
        """返回模型输出文本。"""
        raise NotImplementedError
