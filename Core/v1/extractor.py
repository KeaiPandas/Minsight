# -*- coding: utf-8 -*-
"""V1 抽取器：单次调用直出 JSON（基线方案）。

本质：拼一个 prompt → 单次调用 → 一次 json.loads（naive，无容错、无自修复）。
缺陷：四类信息耦合、无归一、无校验、无证据、格式一崩即整场零产出。
prompt 由 prompts/v1_all.txt 配置。
"""

from shared.schema import safe_json_parse, empty_result
from shared.prompts import render


def extract_v1(case, llm):
    llm.set_case(case)
    raw = llm.complete(render("v1", "v1_all", transcript=case["transcript"]), agent="v1_all")
    data, ok = safe_json_parse(raw, lenient=False)   # naive：不做任何容错
    if not ok:
        return empty_result()
    data["_format_valid"] = True
    return data
