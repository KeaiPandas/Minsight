# -*- coding: utf-8 -*-
"""Load benchmark and demo scenario cases from JSON files."""

import glob
import json
import os

SCENARIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "scenarios",
)


def load_cases(scenario=None):
    """Load all cases or a single scenario from `Core/data/scenarios/*.json`.

    Each scenario file should contain either a JSON array of cases or one JSON
    object. A single object is accepted for small ad-hoc fixtures.
    """
    cases = []
    if scenario:
        files = [os.path.join(SCENARIO_DIR, f"{scenario}.json")]
    else:
        files = sorted(glob.glob(os.path.join(SCENARIO_DIR, "*.json")))
    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            cases.extend(data)
        else:
            cases.append(data)
    return cases


def list_scenarios():
    return sorted(
        os.path.splitext(os.path.basename(path))[0]
        for path in glob.glob(os.path.join(SCENARIO_DIR, "*.json"))
    )
