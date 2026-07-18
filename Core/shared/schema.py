# -*- coding: utf-8 -*-
"""统一的结构化会议纪要 schema 与解析工具。"""

import json
import re

REQUIRED_KEYS = ["participants", "key_points", "action_items", "decisions"]


def empty_result():
    return {"participants": [], "key_points": [], "action_items": [],
            "decisions": [], "_format_valid": False}


def strip_code_fence(text):
    """去掉 ```json ... ``` 围栏与前后多余文字，尽量抠出 JSON 主体。"""
    if not isinstance(text, str):
        return text
    m = re.search(r"\{.*\}", text, flags=re.S)
    return m.group(0) if m else text


def safe_json_parse(raw, repair_fn=None, lenient=True):
    """解析 JSON。
    - lenient=False：纯 json.loads，不做任何容错（V1 的 naive 行为，围栏即失败）。
    - lenient=True：失败时先尝试抠出 JSON 主体。
    - repair_fn：仍失败则调用它修复一次（V2 的自修复）。
    返回 (data or None, ok)。"""
    try:
        return json.loads(raw), True
    except Exception:
        pass
    if lenient:
        try:
            return json.loads(strip_code_fence(raw)), True
        except Exception:
            pass
    if repair_fn is not None:
        try:
            fixed = repair_fn(raw)
            return json.loads(strip_code_fence(fixed)), True
        except Exception:
            return None, False
    return None, False
