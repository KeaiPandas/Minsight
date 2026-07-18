# -*- coding: utf-8 -*-
"""Benchmark and demo runtime seams for Lab."""

import json
import os
import re
import sys
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.join(os.path.dirname(ROOT), "Core")
if CORE_ROOT not in sys.path:
    sys.path.insert(0, CORE_ROOT)

from shared.dataio import list_scenarios, load_cases
from shared.llm import LLMClient
from v1.extractor import extract_v1
from v2.graph import extract_v2_graph

from judge import judge_prediction
from store import BenchmarkStore


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


class BenchmarkRuntime:
    """Owns benchmark lifecycle, business demo lifecycle, and persistence."""

    def __init__(
        self,
        db_path=None,
        results_dir=None,
        load_cases_fn=None,
        list_scenarios_fn=None,
        v1_extractor=None,
        v2_extractor_factory=None,
        judge_fn=None,
        llm_factory=None,
    ):
        self.db_path = db_path or os.path.join(ROOT, "minsight_lab.sqlite")
        self.results_dir = results_dir or os.path.join(ROOT, "results")
        self.load_cases_fn = load_cases_fn or load_cases
        self.list_scenarios_fn = list_scenarios_fn or list_scenarios
        self.v1_extractor = v1_extractor or extract_v1
        self.v2_extractor_factory = v2_extractor_factory or self._default_v2_extractor_factory
        self.judge_fn = judge_fn or judge_prediction
        self.llm_factory = llm_factory or LLMClient

    def store(self):
        store = BenchmarkStore(self.db_path)
        store.init_schema()
        return store

    def list_scenarios(self):
        return self.list_scenarios_fn()

    def list_demo_cases(self):
        return [
            {
                "case_id": case["id"],
                "scenario": case["scenario"],
                "title": f"{case['id']} · {case['scenario']}",
                "transcript_preview": case["transcript"][:180],
                "transcript": case["transcript"],
            }
            for case in self.load_cases_fn(None)
        ]

    def list_runs(self, limit=20):
        return self.store().list_runs(limit=limit)

    def list_meetings(self, limit=20):
        return self.store().list_meetings(limit=limit)

    def delete_run(self, run_id):
        return self.store().delete_run(run_id)

    def create_run(self, scenario=None, plain=False):
        run_id = str(uuid.uuid4())
        v2_impl, _ = self.get_v2_extractor(plain)
        store = self.store()
        store.create_run(run_id=run_id, scenario=scenario, v2_impl=v2_impl)
        return run_id

    def create_demo_meeting(self, title, transcript, scenario=None, source_case_id=None):
        meeting_id = str(uuid.uuid4())
        safe_title = title or f"Meeting {meeting_id[:8]}"
        self.store().create_meeting(meeting_id, safe_title, scenario, source_case_id, transcript)
        return meeting_id

    def resolve_case(self, scenario=None, case_id=None, transcript=None, title=None):
        if case_id:
            for case in self.load_cases_fn(None):
                if case["id"] == case_id:
                    return case
            raise ValueError(f"case not found: {case_id}")
        if transcript and transcript.strip():
            custom_id = f"adhoc_{uuid.uuid4().hex[:8]}"
            return {
                "id": custom_id,
                "scenario": scenario or "ad_hoc",
                "transcript": transcript.strip(),
                "gold": {"participants": [], "key_points": [], "action_items": [], "decisions": []},
                "title": title or "Ad hoc transcript",
            }
        raise ValueError("scenario case_id or transcript is required")

    def get_run_details(self, run_id):
        store = self.store()
        run = store.get_run(run_id)
        if not run:
            return None
        judgements = store.list_judgements(run_id)
        predictions = store.list_predictions(run_id)
        case_results = self._build_case_results(predictions, judgements)
        summary = self.aggregate_judgements(
            [
                {
                    "variant": row["variant"],
                    "score_participants": row["result"]["participants"],
                    "score_key_points": row["result"]["key_points"],
                    "score_action_items": row["result"]["action_items"],
                    "score_decisions": row["result"]["decisions"],
                    "score_overall": row["result"]["overall"],
                }
                for row in judgements
            ]
        )
        return {
            "run": run,
            "summary": summary,
            "judgements": judgements,
            "predictions": predictions,
            "case_results": case_results,
        }

    def get_demo_meeting_details(self, meeting_id):
        store = self.store()
        meeting = store.get_meeting(meeting_id)
        if not meeting:
            return None
        actions = store.list_meeting_actions(meeting_id)
        decisions = store.list_meeting_decisions(meeting_id)
        tasks = store.list_derived_tasks(meeting_id)
        alerts = self._build_cross_meeting_alerts(meeting_id, actions, decisions)
        variants = {
            "v1": meeting.get("v1_json") or {},
            "v2": meeting.get("v2_json") or {},
        }
        return {
            "meeting": meeting,
            "variants": variants,
            "minutes": self._build_minutes_view(meeting),
            "comparison": meeting.get("comparison_json") or self._build_comparison(variants["v1"], variants["v2"]),
            "actions": actions,
            "decisions": decisions,
            "derived_tasks": tasks,
            "alerts": alerts,
        }

    def get_v2_extractor(self, plain=False):
        return self.v2_extractor_factory(plain)

    def aggregate_judgements(self, judgements):
        acc = defaultdict(lambda: defaultdict(list))
        for row in judgements:
            bucket = acc[row["variant"]]
            for key in ("participants", "key_points", "action_items", "decisions", "overall"):
                bucket[key].append(row[f"score_{key}"])
        out = {}
        for variant, bucket in acc.items():
            out[variant] = {
                key: (sum(vals) / len(vals) if vals else 0.0)
                for key, vals in bucket.items()
            }
        return out

    def _build_case_results(self, predictions, judgements):
        by_case = {}
        for row in predictions:
            key = (row["scenario"], row["case_id"])
            case_entry = by_case.setdefault(
                key,
                {
                    "scenario": row["scenario"],
                    "case_id": row["case_id"],
                    "transcript": row["transcript"],
                    "variants": {},
                },
            )
            case_entry["variants"].setdefault(row["variant"], {})["prediction"] = {
                "impl": row["impl"],
                "output": row["output"],
                "routing": row["routing"],
            }
        for row in judgements:
            key = (row["scenario"], row["case_id"])
            case_entry = by_case.setdefault(
                key,
                {
                    "scenario": row["scenario"],
                    "case_id": row["case_id"],
                    "transcript": None,
                    "variants": {},
                },
            )
            variant_entry = case_entry["variants"].setdefault(row["variant"], {})
            variant_entry["judgement"] = row["result"]
            variant_entry["created_at"] = row["created_at"]
        return [by_case[key] for key in sorted(by_case.keys(), key=lambda item: (item[0], item[1]))]

    def _prediction_task(self, case, variant, impl, extractor):
        llm = self.llm_factory()
        output = extractor(case, llm)
        return {
            "case_id": case["id"],
            "scenario": case["scenario"],
            "variant": variant,
            "impl": impl,
            "transcript": case["transcript"],
            "gold": case["gold"],
            "output": output,
            "routing": list(getattr(llm, "call_log", [])),
        }

    def _judge_task(self, prediction_row):
        llm = self.llm_factory()
        result = self.judge_fn(
            llm=llm,
            transcript=prediction_row["transcript"],
            gold=prediction_row["gold"],
            prediction=prediction_row["output"],
        )
        return {
            "case_id": prediction_row["case_id"],
            "scenario": prediction_row["scenario"],
            "variant": prediction_row["variant"],
            "result": result,
        }

    def _extract_variant(self, case, variant, impl, extractor):
        llm = self.llm_factory()
        output = extractor(case, llm)
        return {
            "variant": variant,
            "impl": impl,
            "output": output,
            "routing": list(getattr(llm, "call_log", [])),
        }

    def run_demo_existing(self, meeting_id, case):
        store = self.store()
        store.update_meeting(meeting_id, status="running", phase="extracting", error_message=None, finished_at=None)
        v2_impl, extract_v2 = self.get_v2_extractor(False)
        variants = {
            "v1": ("single-call", self.v1_extractor),
            "v2": (v2_impl, extract_v2),
        }
        try:
            outputs = {}
            with ThreadPoolExecutor(max_workers=2) as pool:
                future_map = {
                    pool.submit(self._extract_variant, case, variant, impl, extractor): variant
                    for variant, (impl, extractor) in variants.items()
                }
                for future in as_completed(future_map):
                    payload = future.result()
                    outputs[payload["variant"]] = payload

            v1_output = outputs["v1"]["output"]
            v2_output = outputs["v2"]["output"]
            comparison = self._build_comparison(v1_output, v2_output)
            store.clear_meeting_assets(meeting_id)
            store.update_meeting(
                meeting_id,
                phase="persisting",
                v1_json=v1_output,
                v2_json=v2_output,
                participants_json=v2_output.get("participants", []),
                key_points_json=v2_output.get("key_points", []),
                comparison_json=comparison,
            )
            self._persist_demo_assets(store, meeting_id, v1_output, v2_output)
            store.update_meeting(meeting_id, status="completed", phase="completed", finished_at=_timestamp())
            return self.get_demo_meeting_details(meeting_id)
        except Exception as exc:
            store.update_meeting(
                meeting_id,
                status="failed",
                phase="failed",
                error_message=str(exc),
                finished_at=_timestamp(),
            )
            raise

    def run_demo(self, title=None, scenario=None, case_id=None, transcript=None):
        case = self.resolve_case(scenario=scenario, case_id=case_id, transcript=transcript, title=title)
        meeting_id = self.create_demo_meeting(
            title=title or case.get("title") or case["id"],
            transcript=case["transcript"],
            scenario=case.get("scenario"),
            source_case_id=case["id"] if case_id else None,
        )
        return self.run_demo_existing(meeting_id=meeting_id, case=case)

    def _persist_demo_assets(self, store, meeting_id, v1_output, v2_output):
        for variant, payload in (("v1", v1_output), ("v2", v2_output)):
            for item in payload.get("action_items", []):
                action_id = store.save_meeting_action(
                    meeting_id=meeting_id,
                    variant=variant,
                    task=item.get("task", ""),
                    owner=item.get("owner"),
                    due=item.get("due"),
                    evidence=item.get("evidence", ""),
                    duplicate_group=self._task_fingerprint(item.get("task", ""), item.get("owner")),
                )
                if variant == "v2":
                    store.save_derived_task(
                        meeting_id=meeting_id,
                        action_id=action_id,
                        title=item.get("task", ""),
                        assignee=item.get("owner"),
                        due_date=item.get("due"),
                        source_evidence=item.get("evidence", ""),
                        status="open",
                    )
            for item in payload.get("decisions", []):
                store.save_meeting_decision(
                    meeting_id=meeting_id,
                    variant=variant,
                    decision=item.get("decision", ""),
                    supersedes=item.get("supersedes"),
                    evidence=item.get("evidence", ""),
                )

    def _build_minutes_view(self, meeting):
        participants = meeting.get("participants_json") or []
        key_points = meeting.get("key_points_json") or []
        v2 = meeting.get("v2_json") or {}
        action_items = v2.get("action_items", [])
        decisions = v2.get("decisions", [])
        summary = []
        if key_points:
            summary.append(f"{len(key_points)} key points captured")
        if action_items:
            summary.append(f"{len(action_items)} action items assigned")
        if decisions:
            summary.append(f"{len(decisions)} decisions recorded")
        return {
            "title": meeting["title"],
            "scenario": meeting.get("scenario") or "ad_hoc",
            "summary_line": " · ".join(summary) if summary else "No structured highlights yet.",
            "participants": participants,
            "key_points": key_points,
            "action_items": action_items,
            "decisions": decisions,
        }

    def _build_comparison(self, v1_output, v2_output):
        def _count(payload, key):
            return len(payload.get(key, []) or [])

        highlights = []
        if not v1_output.get("_format_valid") and v2_output.get("_format_valid"):
            highlights.append("V1 failed strict parsing while V2 recovered through structured validation.")
        if _count(v2_output, "action_items") > _count(v1_output, "action_items"):
            highlights.append("V2 captured more actionable follow-ups and preserved owners or due dates.")
        if any(item.get("evidence") for item in v2_output.get("action_items", [])):
            highlights.append("V2 keeps evidence on action items and decisions so each conclusion can be traced back.")
        if not highlights:
            highlights.append("V2 keeps the same four entity types but with stronger validation and evidence support.")
        return {
            "v1_format_valid": bool(v1_output.get("_format_valid")),
            "v2_format_valid": bool(v2_output.get("_format_valid")),
            "v1_counts": {
                "participants": _count(v1_output, "participants"),
                "key_points": _count(v1_output, "key_points"),
                "action_items": _count(v1_output, "action_items"),
                "decisions": _count(v1_output, "decisions"),
            },
            "v2_counts": {
                "participants": _count(v2_output, "participants"),
                "key_points": _count(v2_output, "key_points"),
                "action_items": _count(v2_output, "action_items"),
                "decisions": _count(v2_output, "decisions"),
            },
            "highlights": highlights,
        }

    def _build_cross_meeting_alerts(self, meeting_id, actions, decisions):
        store = self.store()
        other_actions = store.list_other_actions(meeting_id, variant="v2")
        alerts = []
        seen = set()
        for action in actions:
            if action["variant"] != "v2":
                continue
            fp = self._task_fingerprint(action["task"], action.get("owner"))
            if not fp:
                continue
            for previous in other_actions:
                if previous.get("duplicate_group") != fp:
                    continue
                key = (action["task"], previous["meeting_id"])
                if key in seen:
                    continue
                seen.add(key)
                alerts.append(
                    {
                        "type": "possible_duplicate_action",
                        "title": "Possible duplicate follow-up",
                        "message": f"{action.get('owner') or 'Unassigned'} already has a very similar task in another meeting.",
                        "task": action["task"],
                        "related_meeting_id": previous["meeting_id"],
                        "related_evidence": previous.get("evidence", ""),
                    }
                )
        for decision in decisions:
            if decision["variant"] == "v2" and decision.get("supersedes"):
                alerts.append(
                    {
                        "type": "decision_reversal",
                        "title": "Decision reversal detected",
                        "message": "This decision explicitly supersedes an earlier plan.",
                        "decision": decision["decision"],
                        "supersedes": decision["supersedes"],
                    }
                )
        return alerts

    @staticmethod
    def _task_fingerprint(task, owner):
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", (task or "").lower())
        normalized = " ".join(normalized.split())
        if not normalized:
            return None
        return f"{(owner or '').strip().lower()}::{normalized}"

    def run_benchmark_existing(self, run_id, scenario=None, plain=False):
        store = self.store()
        v2_impl, extract_v2 = self.get_v2_extractor(plain)
        variants = {
            "v1": ("single-call", self.v1_extractor),
            "v2": (v2_impl, extract_v2),
        }
        cases = self.load_cases_fn(scenario)
        prediction_jobs = [
            (case, variant, impl, extractor)
            for case in cases
            for variant, (impl, extractor) in variants.items()
        ]
        total_tasks = len(prediction_jobs) * 2
        store.update_run_status(
            run_id,
            status="running",
            phase="predictions",
            total_tasks=total_tasks,
            completed_tasks=0,
            error_message=None,
            finished_at=None,
        )
        try:
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(prediction_jobs)))) as pool:
                future_map = {
                    pool.submit(self._prediction_task, case, variant, impl, extractor): (case["id"], variant)
                    for case, variant, impl, extractor in prediction_jobs
                }
                for future in as_completed(future_map):
                    case_id, variant = future_map[future]
                    store.update_run_status(run_id, current_case_id=case_id, current_variant=variant)
                    payload = future.result()
                    store.save_prediction(
                        run_id=run_id,
                        case_id=payload["case_id"],
                        scenario=payload["scenario"],
                        variant=payload["variant"],
                        impl=payload["impl"],
                        transcript=payload["transcript"],
                        gold=payload["gold"],
                        output=payload["output"],
                        routing=payload["routing"],
                    )
                    store.increment_completed_tasks(run_id)

            store.update_run_status(run_id, phase="judgements")
            judgements = []
            prediction_rows = store.list_predictions(run_id)
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(prediction_rows)))) as pool:
                future_map = {
                    pool.submit(self._judge_task, row): (row["case_id"], row["variant"])
                    for row in prediction_rows
                }
                for future in as_completed(future_map):
                    case_id, variant = future_map[future]
                    store.update_run_status(run_id, current_case_id=case_id, current_variant=variant)
                    payload = future.result()
                    result = payload["result"]
                    judgements.append(
                        {
                            "variant": payload["variant"],
                            "score_participants": result["participants"],
                            "score_key_points": result["key_points"],
                            "score_action_items": result["action_items"],
                            "score_decisions": result["decisions"],
                            "score_overall": result["overall"],
                        }
                    )
                    store.save_judgement(
                        run_id=run_id,
                        case_id=payload["case_id"],
                        scenario=payload["scenario"],
                        variant=payload["variant"],
                        result=result,
                    )
                    store.increment_completed_tasks(run_id)

            summary = self.aggregate_judgements(judgements)
            os.makedirs(self.results_dir, exist_ok=True)
            report_path = os.path.join(self.results_dir, f"{run_id}.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_id": run_id,
                        "scenario": scenario,
                        "v2_impl": v2_impl,
                        "summary": summary,
                        "prediction_backend": "real (openai-compatible)",
                        "judge_backend": "real (openai-compatible)",
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            store.update_run_status(
                run_id,
                status="completed",
                phase="completed",
                current_case_id=None,
                current_variant=None,
                finished_at=_timestamp(),
            )
            return {
                "run_id": run_id,
                "scenario": scenario,
                "v2_impl": v2_impl,
                "summary": summary,
                "prediction_backend": "real (openai-compatible)",
                "judge_backend": "real (openai-compatible)",
                "db_path": self.db_path,
                "report_path": report_path,
            }
        except Exception as exc:
            store.update_run_status(
                run_id,
                status="failed",
                phase="failed",
                error_message=str(exc),
                finished_at=_timestamp(),
            )
            raise

    def run_benchmark(self, scenario=None, plain=False):
        run_id = self.create_run(scenario=scenario, plain=plain)
        return self.run_benchmark_existing(run_id=run_id, scenario=scenario, plain=plain)

    @staticmethod
    def _default_v2_extractor_factory(_plain):
        return "langgraph", extract_v2_graph
