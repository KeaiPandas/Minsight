# -*- coding: utf-8 -*-
"""Compatibility wrappers over the Lab runtime seam."""

from runtime import BenchmarkRuntime

_RUNTIME = BenchmarkRuntime()


def get_runtime(db_path=None):
    if db_path is None:
        return _RUNTIME
    return BenchmarkRuntime(db_path=db_path)


def get_available_scenarios():
    return _RUNTIME.list_scenarios()


def get_v2_extractor(plain):
    return _RUNTIME.get_v2_extractor(plain)


def aggregate_judgements(judgements):
    return _RUNTIME.aggregate_judgements(judgements)


def run_benchmark_existing(run_id, scenario=None, plain=False, db_path=None):
    return get_runtime(db_path).run_benchmark_existing(
        run_id=run_id,
        scenario=scenario,
        plain=plain,
    )


def run_benchmark(scenario=None, plain=False, db_path=None):
    return get_runtime(db_path).run_benchmark(
        scenario=scenario,
        plain=plain,
    )
