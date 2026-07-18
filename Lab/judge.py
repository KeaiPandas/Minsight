# -*- coding: utf-8 -*-
"""LLM judge：只用评委模型对结构化结果按维度打分。"""

import json
import os

from pydantic import BaseModel

ROOT = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(ROOT, "prompts", "judge.txt")


class JudgeResult(BaseModel):
    participants: float
    key_points: float
    action_items: float
    decisions: float
    overall: float
    strengths: list[str]
    issues: list[str]
    summary: str


def _load_prompt():
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def judge_prediction(llm, transcript, gold, prediction):
    prompt = _load_prompt()
    prompt = prompt.replace("{{TRANSCRIPT}}", transcript)
    prompt = prompt.replace("{{GOLD}}", json.dumps(gold, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{{PREDICTION}}", json.dumps(prediction, ensure_ascii=False, indent=2))
    raw = llm.complete(prompt, agent="lab_judge")
    data = _parse_json(raw)
    parsed = JudgeResult.model_validate(data)
    return parsed.model_dump()


def _parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw[start:end + 1])
    raise ValueError("judge output is not valid JSON")
