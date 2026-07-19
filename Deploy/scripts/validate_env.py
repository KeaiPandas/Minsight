# -*- coding: utf-8 -*-
"""Validate production environment variables before starting Minsight Deploy."""

import os
import sys


REQUIRED = (
    "MINSIGHT_CONFIG_MODE",
    "MINSIGHT_DB_PATH",
    "LLM_LIGHT_API_KEY",
    "LLM_LIGHT_MODEL",
    "LLM_STANDARD_API_KEY",
    "LLM_STANDARD_MODEL",
    "LLM_STRONG_API_KEY",
    "LLM_STRONG_MODEL",
)

PLACEHOLDER_MARKERS = (
    "your-",
    "replace-me",
    "changeme",
    "<",
    ">",
)


def main():
    errors = []
    for key in REQUIRED:
        value = os.getenv(key, "").strip()
        if not value:
            errors.append(f"missing {key}")
            continue
        lowered = value.lower()
        if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{key} still looks like a placeholder")

    mode = os.getenv("MINSIGHT_CONFIG_MODE", "").strip().lower()
    if mode not in {"production", "prod", "deploy"}:
        errors.append("MINSIGHT_CONFIG_MODE must be production/prod/deploy")

    for key in ("MINSIGHT_FEISHU_SYNC_MODE", "MINSIGHT_FEISHU_BASE_SYNC_MODE"):
        value = os.getenv(key, "dry_run").strip().lower()
        if value not in {"dry_run", "lark_cli", "lark-cli", "cli"}:
            errors.append(f"{key} has unsupported value: {value}")

    if errors:
        print("Minsight deploy env validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
