# -*- coding: utf-8 -*-

import json
import tempfile
import unittest
from pathlib import Path
import sys

LAB_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from runtime import BenchmarkRuntime
from helpers import load_fixture


class BenchmarkRuntimeTests(unittest.TestCase):
    def test_workbench_lists_json_scenario_cases(self):
        runtime = BenchmarkRuntime(
            db_path=":memory:",
            llm_factory=lambda: object(),
        )

        cases = runtime.list_demo_cases()
        case_ids = {case["case_id"] for case in cases}

        self.assertGreater(len(cases), 0)
        self.assertIn("rev_01", case_ids)
        self.assertTrue(all(case["transcript"] for case in cases))

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
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=fake_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="demo")

            self.assertEqual(result["v2_impl"], "langgraph")
            self.assertIn("v2", result["summary"])
            self.assertNotIn("v1", result["summary"])
            report_path = Path(result["report_path"])
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["run_id"], result["run_id"])

    def test_runtime_uses_objective_metrics_for_participants_and_keeps_actions_as_judge_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            fixture = load_fixture("objective_metrics_nickname.json")

            def fake_cases(_scenario):
                return [fixture["case"]]

            def fake_v2(_case, _llm):
                return fixture["prediction"]

            def noisy_judge(**_kwargs):
                return fixture["noisy_semantic_judge"]

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["nickname_reference"],
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=noisy_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="nickname_reference")
            scores = result["summary"]["v2"]

            self.assertEqual(scores["participants"], 1.0)
            self.assertEqual(scores["action_items"], fixture["noisy_semantic_judge"]["action_items"])
            self.assertGreater(scores["overall"], 0.0)

    def test_runtime_persists_objective_details_without_changing_summary_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            fixture = load_fixture("objective_metrics_w15.json")

            def fake_cases(_scenario):
                return [fixture["case"]]

            def fake_v2(_case, _llm):
                return fixture["prediction_with_extra_and_bad_evidence"]

            def semantic_judge(**_kwargs):
                return {
                    "participants": 0.0,
                    "key_points": 0.8,
                    "action_items": 0.0,
                    "decisions": 1.0,
                    "overall": 0.7,
                    "summary": "semantic only",
                    "strengths": [],
                    "issues": [],
                }

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["objective_metrics"],
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=semantic_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="objective_metrics")
            details = runtime.get_run_details(result["run_id"])
            judgement = details["case_results"][0]["variants"]["v2"]["judgement"]

            self.assertEqual(
                set(result["summary"]["v2"]),
                {"participants", "key_points", "action_items", "decisions", "overall"},
            )
            self.assertIn("_objective_details", judgement)
            self.assertIn("_objective_scores", judgement)
            self.assertEqual(judgement["_objective_details"]["action_items"]["extra_items"], 1)
            self.assertEqual(judgement["action_items"], 0.0)
            self.assertEqual(judgement["decisions"], 1.0)

    def test_get_run_details_hides_archived_v1_results(self):
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
            self.assertNotIn("v1", case_result["variants"])
            self.assertIn("v2", case_result["variants"])
            self.assertNotIn("v1", details["summary"])
            self.assertEqual(
                case_result["variants"]["v2"]["judgement"]["overall"],
                1.0,
            )

    def test_get_run_details_includes_v2_history_score_deltas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                llm_factory=lambda: object(),
            )
            store = runtime.store()
            store.create_run("previous-run", "demo", "langgraph")
            store.create_run("current-run", "demo", "langgraph")
            store.update_run_status("previous-run", created_at="2026-07-18T01:00:00+00:00")
            store.update_run_status("current-run", created_at="2026-07-18T02:00:00+00:00")
            scores = {
                "previous-run": {
                    "participants": 0.2,
                    "key_points": 0.5,
                    "action_items": 0.7,
                    "decisions": 0.6,
                    "overall": 0.5,
                },
                "current-run": {
                    "participants": 0.4,
                    "key_points": 0.8,
                    "action_items": 0.6,
                    "decisions": 0.6,
                    "overall": 0.6,
                },
            }
            for run_id, result in scores.items():
                store.save_prediction(
                    run_id=run_id,
                    case_id="case-1",
                    scenario="demo",
                    variant="v2",
                    impl="langgraph",
                    transcript="meeting transcript",
                    gold={"participants": []},
                    output={"participants": [run_id]},
                    routing=[],
                )
                store.save_judgement(
                    run_id=run_id,
                    case_id="case-1",
                    scenario="demo",
                    variant="v2",
                    result={
                        **result,
                        "summary": run_id,
                        "strengths": [],
                        "issues": [],
                    },
                )

            details = runtime.get_run_details("current-run")
            delta = details["case_results"][0]["v2_history_delta"]

            self.assertEqual(delta["basis"], "current_v2_minus_previous_v2")
            self.assertEqual(delta["previous_run_id"], "previous-run")
            self.assertAlmostEqual(delta["delta"]["participants"], 0.2)
            self.assertAlmostEqual(delta["delta"]["key_points"], 0.3)
            self.assertAlmostEqual(delta["delta"]["action_items"], -0.1)
            self.assertAlmostEqual(delta["delta"]["decisions"], 0.0)
            self.assertAlmostEqual(delta["delta"]["overall"], 0.1)

    def test_get_run_details_includes_summary_history_delta_for_same_scenario(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"
            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                llm_factory=lambda: object(),
            )
            store = runtime.store()
            store.create_run("previous-run", "demo", "langgraph")
            store.create_run("current-run", "demo", "langgraph")
            store.update_run_status("previous-run", created_at="2026-07-18T01:00:00+00:00", status="completed")
            store.update_run_status("current-run", created_at="2026-07-18T02:00:00+00:00", status="completed")
            for run_id, score in (
                ("previous-run", 0.5),
                ("current-run", 0.75),
            ):
                store.save_judgement(
                    run_id=run_id,
                    case_id="case-1",
                    scenario="demo",
                    variant="v2",
                    result={
                        "participants": score,
                        "key_points": score,
                        "action_items": score,
                        "decisions": score,
                        "overall": score,
                        "summary": run_id,
                        "strengths": [],
                        "issues": [],
                    },
                )

            details = runtime.get_run_details("current-run")
            delta = details["summary_history_delta"]

            self.assertEqual(delta["previous_run_id"], "previous-run")
            self.assertEqual(delta["previous_created_at"], "2026-07-18T01:00:00+00:00")
            self.assertEqual(set(delta["current"]), {"participants", "key_points", "action_items", "decisions", "overall"})
            self.assertAlmostEqual(delta["current"]["overall"], 0.75)
            self.assertAlmostEqual(delta["previous"]["overall"], 0.5)
            self.assertAlmostEqual(delta["delta"]["overall"], 0.25)

    def test_runtime_records_current_agent_errors_without_failing_run(self):
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

            def broken_v2(_case, _llm):
                raise json.JSONDecodeError("Expecting value", "```json", 0)

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
                v2_extractor_factory=lambda plain: ("langgraph", broken_v2),
                judge_fn=fake_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="demo")
            details = runtime.get_run_details(result["run_id"])
            v2_prediction = details["case_results"][0]["variants"]["v2"]["prediction"]["output"]

            self.assertEqual(details["run"]["status"], "completed")
            self.assertEqual(v2_prediction["_extract_error"], "JSONDecodeError")
            self.assertEqual(result["summary"]["v2"]["overall"], 0.0)

    def test_runtime_records_judge_errors_without_failing_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite"

            def fake_cases(_scenario):
                return [
                    {
                        "id": "case-1",
                        "scenario": "demo",
                        "transcript": "meeting transcript",
                        "gold": {"participants": [{"name": "Alice", "role": "PM"}]},
                    }
                ]

            def fake_v2(_case, _llm):
                return {
                    "participants": [{"name": "Alice", "role": "PM"}],
                    "key_points": [],
                    "action_items": [],
                    "decisions": [],
                }

            def broken_judge(**_kwargs):
                raise json.JSONDecodeError("Expecting ',' delimiter", "{", 251)

            runtime = BenchmarkRuntime(
                db_path=str(db_path),
                results_dir=str(Path(tmpdir) / "results"),
                load_cases_fn=fake_cases,
                list_scenarios_fn=lambda: ["demo"],
                v2_extractor_factory=lambda plain: ("langgraph", fake_v2),
                judge_fn=broken_judge,
                llm_factory=lambda: object(),
            )

            result = runtime.run_benchmark(scenario="demo")
            details = runtime.get_run_details(result["run_id"])
            judgement = details["case_results"][0]["variants"]["v2"]["judgement"]

            self.assertEqual(details["run"]["status"], "completed")
            self.assertEqual(judgement["_judge_error"], "JSONDecodeError")
            self.assertIn("Expecting ',' delimiter", judgement["_judge_error_message"])
            self.assertEqual(judgement["participants"], 1.0)
            self.assertEqual(judgement["overall"], result["summary"]["v2"]["overall"])

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
