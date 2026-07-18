# -*- coding: utf-8 -*-
"""V1 baseline: one prompt, one LLM call, one json.loads.

This intentionally mirrors the assignment-style baseline. It does not use
schema validation, repair, evidence enrichment, or post-processing.
"""

import json


def extract_meeting_minutes(transcript: str, llm) -> dict:
    prompt = f"""你是专业的会议纪要助手。请从以下会议转写文本中提取：
1. 参会人列表（含角色）
2. 关键讨论要点
3. 待办事项（含负责人和截止时间）
4. 决策结论

要求输出 JSON 格式。

转写文本：
{transcript}"""

    response = llm.complete(prompt, agent="v1_all")
    return json.loads(response)


def extract_v1(case, llm):
    llm.set_case(case)
    return extract_meeting_minutes(case["transcript"], llm)
