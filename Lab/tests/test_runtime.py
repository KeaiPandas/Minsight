# -*- coding: utf-8 -*-

import json
import tempfile
import unittest
from pathlib import Path
import sys

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from runtime import BenchmarkRuntime


class BenchmarkRuntimeTests(unittest.TestCase):
    def test_runtime_executes_run_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            results_dir = Path(tmpdir) / "results"

            def fake_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "meeting transcript",
                        "gold": {"participants": []},
                    }
                ]

            def fake_v1(case, _llm):
                return {"variant": "v1", "case_id": case["id"]}

            def fake_v2(case, _llm):
                return {"variant": "v2", "case_id": case["id"]}

            def fake_judge(**_kwargs):
                return {
                    "participants": 1.0,
                    "key_points": 0.9,
                    "action_items": 0.8,
                    "decisions": 1.0,
                    "overall": 0.925,
                    "summary": "ok",
                    "strengths": ["clear"],
                    "issues": [],
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(results_dir),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["demo"],
                v1_extractor=fake_v1,
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=fake_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="demo")

            self.assertEqual(result["v2_impl"], "langgraph")
            self.assertIn("v1", result["summary"])
            self.assertIn("v2", result["summary"])
            report_path = Path(result["report_path"])
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["run_id"], result["run_id"])

    def test_get_run_details_groups_results_by_case_and_variant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                llm_factory=lambda: object(),
            )
            store = runtime.store()
            store.create_run("run-1", "demo", "langgraph")
            for variant in ("v1", "v2"):
                store.save_prediction(
                    run_id="run-1",
                    case_id="case-1",
                    scenario="demo",
                    variant=variant,
                    impl="single-call" if variant == "v1" else "langgraph",
                    transcript="meeting transcript",
                    gold={"participants": []},
                    output={"participants": [variant]},
                    routing=[],
                )
                store.save_judgement(
                    run_id="run-1",
                    case_id="case-1",
                    scenario="demo",
                    variant=variant,
                    result={
                        "participants": 1.0 if variant == "v2" else 0.0,
                        "key_points": 1.0,
                        "action_items": 1.0,
                        "decisions": 1.0,
                        "overall": 1.0 if variant == "v2" else 0.2,
                        "summary": variant,
                        "strengths": [],
                        "issues": [],
                    },
                )

            details = runtime.get_run_details("run-1")

            self.assertEqual(len(details["case_results"]), 1)
            case_result = details["case_results"][0]
            self.assertEqual(case_result["case_id"], "case-1")
            self.assertIn("v1", case_result["variants"])
            self.assertIn("v2", case_result["variants"])
            self.assertEqual(
                case_result["variants"]["v2"]["judgement"]["overall"],
                1.0,
            )

    def test_runtime_records_extractor_errors_without_failing_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"

            def fake_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "meeting transcript",
                        "gold": {"participants": []},
                    }
                ]

            def broken_v1(_case, _llm):
                raise json.JSONDecodeError("Expecting value", "```json", 0)

            def fake_v2(case, _llm):
                return {
                    "participants": [],
                    "key_points": [],
                    "action_items": [],
                    "decisions": [],
                    "case_id": case["id"],
                }

            def fake_judge(**kwargs):
                prediction = kwargs["prediction"]
                failed = bool(prediction.get("_extract_error"))
                return {
                    "participants": 0.0 if failed else 1.0,
                    "key_points": 0.0 if failed else 1.0,
                    "action_items": 0.0 if failed else 1.0,
                    "decisions": 0.0 if failed else 1.0,
                    "overall": 0.0 if failed else 1.0,
                    "summary": "failed" if failed else "ok",
                    "strengths": [],
                    "issues": ["extractor failed"] if failed else [],
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["demo"],
                v1_extractor=broken_v1,
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=fake_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="demo")
            details = runtime.get_run_details(result["run_id"])
            v1_prediction = details["case_results"][0]["variants"]["v1"]["prediction"]["output"]

            self.assertEqual(details["run"]["status"], "completed")
            self.assertEqual(v1_prediction["_extract_error"], "JSONDecodeError")
            self.assertEqual(result["summary"]["v1"]["overall"], 0.0)

    def test_demo_run_persists_minutes_tasks_and_duplicate_alerts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"

            cases = [
                {
                    "id": "case-1",
                    "scenario": "demo",
                    "transcript": "meeting transcript",
                    "gold": {"participants": []},
                }
            ]

            def fake_load_cases(_scenario):
                return cases

            def fake_v1(_case, _llm):
                raise AssertionError("workbench should not run v1")

            def fake_v2(_case, _llm):
                return {
                    "participants": [{"name": "Alice", "role": "PM"}],
                    "key_points": [{"topic": "Launch", "summary": "Launch is delayed."}],
                    "action_items": [
                        {
                            "task": "Ship review doc",
                            "owner": "Alice",
                            "due": "2026-07-20",
                            "evidence": "Alice: I will ship the review doc.",
                        }
                    ],
                    "decisions": [
                        {
                            "decision": "Delay launch to next week",
                            "supersedes": "Launch this Friday",
                            "evidence": "Delay it.",
                        }
                    ],
                    "_format_valid": True,
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_load_cases,
                list_scenarios_fn=lambda: ["demo"],
                v1_extractor=fake_v1,
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                llm_factory=lambda: object(),
            )

            first = runtime.run_demo(title="Review 1", transcript="meeting transcript")
            second = runtime.run_demo(title="Review 2", transcript="meeting transcript")

            self.assertEqual(first["meeting"]["status"], "completed")
            self.assertNotIn("comparison", first)
            self.assertEqual(first["output"]["participants"][0]["name"], "Alice")
            self.assertEqual(first["derived_tasks"][0]["assignee"], "Alice")
            self.assertTrue(any(alert["type"] == "decision_reversal" for alert in first["alerts"]))
            self.assertTrue(any(alert["type"] == "possible_duplicate_action" for alert in second["alerts"]))


if __name__ == "__main__":
    unittest.main()
