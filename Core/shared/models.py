# -*- coding: utf-8 -*-
"""结构化会议纪要的 pydantic 契约（仅 V2 使用；V1 保持 naive 以对照其脆弱）。

用类型 + 校验器把 schema 与业务规则声明成显式契约：
- 待办 due 缺失如实置 None（不臆造），owner 必填；
- 每个子抽取器有自己的输出模型，哪一步不合规就在哪一步暴露、重试。
校验失败（含字段级 ValidationError）会带错误消息喂回 repair agent 修复。
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator

from shared.schema import strip_code_fence

# 视为“未提及截止时间”的取值，一律归一为 None，杜绝臆造
_EMPTY_DUE = {"", "未提及", "无", "n/a", "none", "null", "待定", "tbd"}


# ---------- 实体 ----------

class Participant(BaseModel):
    name: str
    role: str = ""


class KeyPoint(BaseModel):
    topic: str
    summary: str = ""


class ActionItem(BaseModel):
    task: str
    owner: str
    due: Optional[str] = None
    evidence: str = ""

    @field_validator("due", mode="before")
    @classmethod
    def _normalize_due(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() in _EMPTY_DUE:
            return None                      # 缺失如实置空，不臆造
        return v

    @field_validator("owner")
    @classmethod
    def _owner_required(cls, v):
        if not v or not v.strip():
            raise ValueError("owner is required")
        return v


class Decision(BaseModel):
    decision: str
    supersedes: Optional[str] = None
    evidence: str = ""


# ---------- 各子抽取器的输出模型 ----------

class ParticipantsOut(BaseModel):
    participants: List[Participant]
    alias_map: Dict[str, str] = {}


class KeyPointsOut(BaseModel):
    key_points: List[KeyPoint]


class ActionsDecisionsOut(BaseModel):
    action_items: List[ActionItem]
    decisions: List[Decision]


class DecisionsOut(BaseModel):
    decisions: List[Decision]


# ---------- 解析 + 校验（含带错误消息的自修复回环）----------

def parse_as(model_cls, raw, repair_fn=None):
    """把模型输出解析并按 model_cls 校验。
    失败（JSON 非法或字段级 ValidationError）时，若给了 repair_fn，
    则带错误消息让模型修一次再校验（局部 ReAct）。返回 (instance or None, ok)。"""
    def _attempt(text):
        data = json.loads(strip_code_fence(text))
        return model_cls.model_validate(data)

    try:
        return _attempt(raw), True
    except (json.JSONDecodeError, ValidationError) as err:
        if repair_fn is None:
            return None, False
        try:
            return _attempt(repair_fn(raw, str(err))), True
        except Exception:
            return None, False
