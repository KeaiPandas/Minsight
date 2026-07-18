# -*- coding: utf-8 -*-
"""Lab CLI entrypoint."""

import argparse

from service import run_benchmark


def _print_summary(summary):
    print("\n" + "=" * 78)
    print("  Lab Summary (LLM judge)")
    print("=" * 78)
    print(
        f"  {'variant':<10}{'participants':>14}{'key_points':>14}"
        f"{'actions':>12}{'decisions':>12}{'overall':>12}"
    )
    print("  " + "-" * 72)
    for variant, scores in sorted(summary.items()):
        print(
            f"  {variant:<10}"
            f"{scores['participants']:>14.3f}"
            f"{scores['key_points']:>14.3f}"
            f"{scores['action_items']:>12.3f}"
            f"{scores['decisions']:>12.3f}"
            f"{scores['overall']:>12.3f}"
        )
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    result = run_benchmark(scenario=args.scenario, db_path=args.db)
    print(f"[lab] run_id={result['run_id']}")
    print(f"[lab] db={result['db_path']}")
    print(f"[lab] prediction backend={result['prediction_backend']}")
    print(f"[lab] judge backend={result['judge_backend']}")
    _print_summary(result["summary"])
    print(f"\n[lab] wrote {result['report_path']}")


if __name__ == "__main__":
    main()
