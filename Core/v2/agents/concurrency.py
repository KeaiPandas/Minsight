# -*- coding: utf-8 -*-
"""Small concurrency helpers for segment-level LLM mapping."""

import os
from concurrent.futures import ThreadPoolExecutor


DEFAULT_SEGMENT_WORKERS = 4


def map_segments(fn, segments):
    """Map segment work concurrently while preserving input order."""
    items = list(segments)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=segment_workers(len(items))) as pool:
        return list(pool.map(fn, items))


def segment_workers(count):
    try:
        configured = int(os.getenv("MINSIGHT_SEGMENT_WORKERS", str(DEFAULT_SEGMENT_WORKERS)))
    except ValueError:
        configured = DEFAULT_SEGMENT_WORKERS
    return max(1, min(configured, max(1, count)))
