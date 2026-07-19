# -*- coding: utf-8 -*-
"""Minimal deploy smoke check for a running Minsight Deploy server."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen


def main(base_url):
    base = base_url.rstrip("/")
    health = _get_json(f"{base}/health")
    if health.get("status") != "ok":
        raise SystemExit(f"health check failed: {health}")

    cases = _get_json(f"{base}/api/demo/cases")
    if "cases" not in cases:
        raise SystemExit(f"demo cases missing: {cases}")

    for path in ("/api/run", "/api/runs", "/api/scenarios"):
        try:
            urlopen(f"{base}{path}", timeout=10)
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise SystemExit(f"unexpected status for {path}: {exc.code}") from exc
        raise SystemExit(f"benchmark path should not be exposed: {path}")

    print("ok")


def _get_json(url):
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"
    main(target)
