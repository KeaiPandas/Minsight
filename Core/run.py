# -*- coding: utf-8 -*-
"""Core entrypoint for running V1 or V2 extractors."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.dataio import load_cases
from shared.llm import LLMClient
from v1.extractor import extract_v1
from v2.graph import extract_v2_graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["v1", "v2"], default="v2")
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()

    llm = LLMClient()
    print(f"[Core] version={args.version}  LLM backend={llm.mode}")

    if args.version == "v1":
        impl = "single-call"
        extractor = extract_v1
    else:
        impl = "langgraph"
        extractor = extract_v2_graph
    print(f"[Core] impl={impl}")

    for case in load_cases(args.scenario):
        out = extractor(case, llm)
        print(f"\n# {case['id']} ({case['scenario']})")
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
