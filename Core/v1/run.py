# -*- coding: utf-8 -*-
"""V1 独立入口：python v1/run.py [--scenario NAME]"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.llm import LLMClient
from shared.dataio import load_cases
from v1.extractor import extract_v1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()
    llm = LLMClient()
    print(f"[V1] LLM backend = {llm.mode}")
    for case in load_cases(args.scenario):
        out = extract_v1(case, llm)
        print(f"\n# {case['id']} ({case['scenario']}) format_valid={out.get('_format_valid')}")
        print(json.dumps({
            "participants": [p.get("name") for p in out.get("participants", [])],
            "action_items": [(a.get("task"), a.get("owner"), a.get("due"))
                             for a in out.get("action_items", [])],
            "decisions": [d.get("decision") for d in out.get("decisions", [])],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
