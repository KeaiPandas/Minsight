# -*- coding: utf-8 -*-
"""Production-facing workbench runtime.

Benchmark execution, LLM judge scoring, and run archives intentionally remain
outside this module. This runtime owns only the deployable meeting workbench
flow.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEPLOY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DEPLOY_ROOT.parent
CORE_ROOT = PROJECT_ROOT / "Core"

os.environ.setdefault("MINSIGHT_CONFIG_MODE", "production")

for path in (PROJECT_ROOT, CORE_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shared.dataio import load_cases  # noqa: E402
from shared.llm import LLMClient  # noqa: E402
from v2.graph import extract_v2_graph  # noqa: E402

try:
    from .integrations.feishu_base import build_decision_sink  # noqa: E402
    from .integrations.feishu_tasks import build_task_sink  # noqa: E402
except ImportError:  # pragma: no cover - script execution path
    from integrations.feishu_base import build_decision_sink  # noqa: E402
    from integrations.feishu_tasks import build_task_sink  # noqa: E402

try:
    from .store import WorkbenchStore  # noqa: E402
except ImportError:  # pragma: no cover - script execution path
    from store import WorkbenchStore  # noqa: E402


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


class WorkbenchRuntime:
    """Owns deployable meeting extraction, persistence, and sync flows."""

    def __init__(
        self,
        db_path=None,
        load_cases_fn=None,
        v2_extractor_factory=None,
        llm_factory=None,
        task_sink_factory=None,
        decision_sink_factory=None,
    ):
        self.db_path = db_path or str(DEPLOY_ROOT / "minsight_deploy.sqlite")
        self.load_cases_fn = load_cases_fn or load_cases
        self.v2_extractor_factory = v2_extractor_factory or self._default_v2_extractor_factory
        self.llm_factory = llm_factory or LLMClient
        self.task_sink_factory = task_sink_factory or build_task_sink
        self.decision_sink_factory = decision_sink_factory or build_decision_sink

    def store(self):
        store = WorkbenchStore(self.db_path)
        store.init_schema()
        return store

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

    def list_meetings(self, limit=20):
        return self.store().list_meetings(limit=limit)

    def recover_interrupted_meetings(self, limit=1000):
        store = self.store()
        recovered = []
        for meeting in store.list_meetings(limit=limit):
            if meeting.get("status") not in {"queued", "running"}:
                continue
            store.update_meeting(
                meeting["meeting_id"],
                status="failed",
                phase="interrupted",
                error_message="The in-memory worker was interrupted, likely because the server restarted.",
                finished_at=_timestamp(),
            )
            recovered.append(meeting["meeting_id"])
        return recovered

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

    def get_demo_meeting_details(self, meeting_id):
        store = self.store()
        meeting = store.get_meeting(meeting_id)
        if not meeting:
            return None
        actions = store.list_meeting_actions(meeting_id)
        decisions = self._public_decisions(store.list_meeting_decisions(meeting_id))
        tasks = store.list_derived_tasks(meeting_id)
        alerts = self._build_cross_meeting_alerts(meeting_id, actions, decisions)
        v2_output = meeting.get("v2_json") or {}
        return {
            "meeting": meeting,
            "output": v2_output,
            "variants": {"v2": v2_output},
            "minutes": self._build_minutes_view(meeting),
            "actions": actions,
            "decisions": decisions,
            "derived_tasks": tasks,
            "alerts": alerts,
        }

    def delete_demo_meeting(self, meeting_id):
        return self.store().delete_meeting(meeting_id)

    @staticmethod
    def _public_decisions(decisions):
        public = []
        for decision in decisions:
            item = dict(decision)
            item["base_url"] = item.get("base_external_url")
            public.append(item)
        return public

    def run_demo(self, title=None, scenario=None, case_id=None, transcript=None):
        case = self.resolve_case(scenario=scenario, case_id=case_id, transcript=transcript, title=title)
        meeting_id = self.create_demo_meeting(
            title=title or case.get("title") or case["id"],
            transcript=case["transcript"],
            scenario=case.get("scenario"),
            source_case_id=case["id"] if case_id else None,
        )
        return self.run_demo_existing(meeting_id=meeting_id, case=case)

    def run_demo_existing(self, meeting_id, case):
        store = self.store()
        store.update_meeting(meeting_id, status="running", phase="extracting", error_message=None, finished_at=None)
        v2_impl, extract_v2 = self.get_v2_extractor()
        try:
            payload = self._extract_variant(case, "v2", v2_impl, extract_v2)
            v2_output = payload["output"]
            store.clear_meeting_assets(meeting_id)
            store.update_meeting(
                meeting_id,
                phase="persisting",
                v1_json=None,
                v2_json=v2_output,
                participants_json=v2_output.get("participants", []),
                key_points_json=v2_output.get("key_points", []),
                comparison_json=None,
            )
            self._persist_demo_assets(store, meeting_id, v2_output)
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

    def sync_demo_tasks_to_feishu(self, meeting_id, mode=None, force=False, tasklist_id=None):
        store = self.store()
        meeting = store.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"meeting not found: {meeting_id}")
        tasks = store.list_derived_tasks(meeting_id)
        sink = self.task_sink_factory(mode)
        if tasklist_id and hasattr(sink, "tasklist_id"):
            sink.tasklist_id = tasklist_id
        results = []
        for task in tasks:
            if task.get("sync_status") == "synced" and not force:
                results.append(
                    {
                        "task_id": task["id"],
                        "provider": task.get("external_provider") or "feishu",
                        "status": "skipped",
                        "external_id": task.get("external_id"),
                        "external_url": task.get("external_url"),
                        "payload": task.get("sync_payload") or {},
                        "error": None,
                        "reason": "already_synced",
                    }
                )
                continue
            result = sink.push_task(task)
            store.update_derived_task_sync(
                task_id=task["id"],
                provider=result.get("provider", "feishu"),
                sync_status=result.get("status", "failed"),
                external_id=result.get("external_id"),
                external_url=result.get("external_url"),
                sync_error=result.get("error"),
                sync_payload=result.get("payload"),
                assignee_open_id=result.get("assignee_open_id"),
                assignee_resolution_status=result.get("assignee_resolution_status"),
                assignee_resolution_error=result.get("assignee_resolution_error"),
            )
            results.append({"task_id": task["id"], **result})
        return {
            "meeting_id": meeting_id,
            "mode": getattr(sink, "mode", mode or "dry_run"),
            "force": bool(force),
            "tasklist_id": tasklist_id or getattr(sink, "tasklist_id", None),
            "tasks": results,
        }

    def sync_demo_decisions_to_feishu_base(self, meeting_id, mode=None, force=False):
        store = self.store()
        meeting = store.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"meeting not found: {meeting_id}")
        decisions = store.list_meeting_decisions(meeting_id)
        sink = self.decision_sink_factory(mode)
        results = []
        for decision in decisions:
            if decision.get("base_sync_status") == "synced" and not force:
                results.append(
                    {
                        "decision_id": decision["id"],
                        "provider": decision.get("base_external_provider") or "feishu_base",
                        "status": "skipped",
                        "external_id": decision.get("base_external_id"),
                        "external_url": decision.get("base_external_url"),
                        "payload": decision.get("base_sync_payload") or {},
                        "error": None,
                        "reason": "already_synced",
                    }
                )
                continue
            result = sink.push_decision(meeting, decision)
            store.update_meeting_decision_sync(
                decision_id=decision["id"],
                provider=result.get("provider", "feishu_base"),
                sync_status=result.get("status", "failed"),
                external_id=result.get("external_id"),
                external_url=result.get("external_url"),
                sync_error=result.get("error"),
                sync_payload=result.get("payload"),
            )
            results.append({"decision_id": decision["id"], **result})
        return {
            "meeting_id": meeting_id,
            "mode": getattr(sink, "mode", mode or "dry_run"),
            "force": bool(force),
            "decisions": results,
        }

    def get_v2_extractor(self):
        return self.v2_extractor_factory(False)

    def _extract_variant(self, case, variant, impl, extractor):
        llm = self.llm_factory()
        try:
            output = extractor(case, llm)
        except Exception as exc:
            output = {
                "_extract_error": type(exc).__name__,
                "_error_message": str(exc),
                "participants": [],
                "key_points": [],
                "action_items": [],
                "decisions": [],
            }
        return {
            "variant": variant,
            "impl": impl,
            "output": output,
            "routing": list(getattr(llm, "call_log", [])),
        }

    def _persist_demo_assets(self, store, meeting_id, v2_output):
        for item in v2_output.get("action_items", []):
            action_id = store.save_meeting_action(
                meeting_id=meeting_id,
                variant="v2",
                task=item.get("task", ""),
                owner=item.get("owner"),
                due=item.get("due"),
                evidence=item.get("evidence", ""),
                duplicate_group=self._task_fingerprint(item.get("task", ""), item.get("owner")),
            )
            store.save_derived_task(
                meeting_id=meeting_id,
                action_id=action_id,
                title=item.get("task", ""),
                assignee=item.get("owner"),
                due_date=item.get("due"),
                source_evidence=item.get("evidence", ""),
                status="open",
            )
        for item in v2_output.get("decisions", []):
            store.save_meeting_decision(
                meeting_id=meeting_id,
                variant="v2",
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

    @staticmethod
    def _default_v2_extractor_factory(_plain):
        return "langgraph", extract_v2_graph
