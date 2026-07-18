# -*- coding: utf-8 -*-
"""V2 standalone entrypoint: python v2/run.py [--scenario NAME]."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.dataio import load_cases
from shared.llm import LLMClient
from v2.graph import extract_v2_graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()

    llm = LLMClient()
    print(f"[V2] impl=langgraph  LLM backend={llm.mode}")

    for case in load_cases(args.scenario):
        out = extract_v2_graph(case, llm)
        print(f"\n# {case['id']} ({case['scenario']})")
        print(
            json.dumps(
                {
                    "participants": [p.get("name") for p in out.get("participants", [])],
                    "action_items": [
                        (a.get("task"), a.get("owner"), a.get("due"))
                        for a in out.get("action_items", [])
                    ],
                    "decisions": [d.get("decision") for d in out.get("decisions", [])],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
