# -*- coding: utf-8 -*-
"""测试集读写：按场景加载 JSONL 数据集。"""

import glob
import json
import os

SCENARIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "scenarios")


def load_cases(scenario=None):
    """加载测试用例。scenario=None 加载全部场景；否则只加载指定场景文件。"""
    cases = []
    if scenario:
        files = [os.path.join(SCENARIO_DIR, f"{scenario}.jsonl")]
    else:
        files = sorted(glob.glob(os.path.join(SCENARIO_DIR, "*.jsonl")))
    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    cases.append(json.loads(line))
    return cases


def list_scenarios():
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(SCENARIO_DIR, "*.jsonl")))
