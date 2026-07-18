# -*- coding: utf-8 -*-
"""Deterministic objective metrics for benchmark scoring."""

from difflib import SequenceMatcher
import re

from shared.meeting_info import build_roster_aliases, get_meeting_info


_STOPWORDS = {
    "the",
    "and",
    "for",
    "this",
    "that",
    "was",
    "were",
    "will",
    "should",
    "please",
    "meeting",
}


def score_objective_dimensions(case, prediction):
    """Score objective dimensions that should not depend on LLM judge variance.

    Returns only dimensions that have enough gold data to score. Semantic
    dimensions such as key_points and decisions stay with the judge.
    """
    gold = case.get("gold", {})
    alias_map = build_roster_aliases(get_meeting_info(case))
    scores = {}
    details = {}

    if gold.get("participants"):
        score, detail = _participant_score(
            gold.get("participants", []),
            prediction.get("participants", []),
            alias_map,
        )
        scores["participants"] = score
        details["participants"] = detail
    if gold.get("action_items"):
        score, detail = _action_item_score(
            gold.get("action_items", []),
            prediction.get("action_items", []),
            alias_map,
        )
        scores["action_items"] = score
        details["action_items"] = detail

    require_evidence = _case_requires_evidence(gold)
    format_score, format_detail = _format_valid_score(prediction, require_evidence=require_evidence)
    evidence_score, evidence_detail = _evidence_score(
        case.get("transcript", ""),
        prediction,
        require_evidence=require_evidence,
    )
    scores["format_valid"] = format_score
    scores["evidence"] = evidence_score
    details["format_valid"] = format_detail
    details["evidence"] = evidence_detail

    # Keep dimension scores at the top level for older tests/callers, while
    # exposing W1.5 details through explicit nested fields.
    return {**scores, "scores": scores, "details": details}


def combine_scores(semantic_scores, objective_scores):
    """Overlay deterministic scores onto semantic judge output."""
    result = dict(semantic_scores)
    scores = objective_scores.get("scores", objective_scores)
    for key, value in scores.items():
        if key != "participants":
            continue
        result[key] = value
    if "_objective_details" not in result and objective_scores.get("details"):
        result["_objective_details"] = objective_scores["details"]
    result["_objective_scores"] = scores
    result["overall"] = _overall(result)
    return result


def _participant_score(gold_participants, predicted_participants, alias_map):
    gold_names = {_canonical_name(item.get("name"), alias_map) for item in gold_participants}
    predicted_names = {_canonical_name(item.get("name"), alias_map) for item in predicted_participants}
    gold_names.discard("")
    predicted_names.discard("")
    return _f1(gold_names, predicted_names), {
        "gold": sorted(gold_names),
        "predicted": sorted(predicted_names),
        "matched": sorted(gold_names & predicted_names),
    }


def _action_item_score(gold_items, predicted_items, alias_map):
    if not gold_items:
        return None, {"gold_count": 0, "predicted_count": len(predicted_items or []), "matches": []}
    used = set()
    item_scores = []
    matches = []
    for gold in gold_items:
        best = None
        best_idx = None
        for idx, predicted in enumerate(predicted_items or []):
            if idx in used:
                continue
            similarity = _task_similarity(gold.get("task", ""), predicted.get("task", ""), alias_map)
            if similarity < 0.35:
                continue
            if best is None or similarity > best:
                best = similarity
                best_idx = idx
        if best_idx is None:
            item_scores.append(0.0)
            matches.append(
                {
                    "gold_task": gold.get("task", ""),
                    "predicted_task": None,
                    "task_similarity": 0.0,
                    "owner_match": False,
                    "due_match": False,
                    "score": 0.0,
                }
            )
            continue
        used.add(best_idx)
        predicted = predicted_items[best_idx]
        owner_ok = _canonical_name(gold.get("owner"), alias_map) == _canonical_name(predicted.get("owner"), alias_map)
        due_ok = (gold.get("due") or None) == (predicted.get("due") or None)
        item_score = 0.4 + (0.35 if owner_ok else 0.0) + (0.25 if due_ok else 0.0)
        item_scores.append(item_score)
        matches.append(
            {
                "gold_task": gold.get("task", ""),
                "predicted_task": predicted.get("task", ""),
                "task_similarity": _clamp(best),
                "owner_match": owner_ok,
                "due_match": due_ok,
                "score": _clamp(item_score),
            }
        )
    predicted_count = len(predicted_items or [])
    matched_count = len(used)
    extra_items = max(0, predicted_count - matched_count)
    precision_penalty = (matched_count / predicted_count) if predicted_count else 1.0
    recall_quality = sum(item_scores) / len(item_scores)
    return _clamp(recall_quality * precision_penalty), {
        "gold_count": len(gold_items),
        "predicted_count": predicted_count,
        "matched_count": matched_count,
        "extra_items": extra_items,
        "precision_penalty": _clamp(precision_penalty),
        "matches": matches,
    }


def _format_valid_score(prediction, require_evidence=False):
    required_arrays = ("participants", "key_points", "action_items", "decisions")
    missing_or_invalid_arrays = [
        key for key in required_arrays if not isinstance(prediction.get(key), list)
    ]
    invalid_due_values = []
    empty_action_owners = 0
    empty_evidence_items = 0
    for item in prediction.get("action_items", []) or []:
        owner = str(item.get("owner") or "").strip()
        if not owner:
            empty_action_owners += 1
        due = item.get("due")
        if due not in (None, "") and not _is_iso_date(str(due)):
            invalid_due_values.append(str(due))
        if require_evidence and not str(item.get("evidence") or "").strip():
            empty_evidence_items += 1
    for item in prediction.get("decisions", []) or []:
        if require_evidence and not str(item.get("evidence") or "").strip():
            empty_evidence_items += 1
    issues = (
        len(missing_or_invalid_arrays)
        + len(invalid_due_values)
        + empty_action_owners
        + empty_evidence_items
    )
    return _clamp(1.0 - (issues * 0.15)), {
        "missing_or_invalid_arrays": missing_or_invalid_arrays,
        "invalid_due_values": invalid_due_values,
        "empty_action_owners": empty_action_owners,
        "empty_evidence_items": empty_evidence_items,
    }


def _evidence_score(transcript, prediction, require_evidence=False):
    if not require_evidence:
        return 1.0, {"checked": 0, "matched": 0, "missing": 0, "misses": []}
    normalized_transcript = _normalize_evidence(transcript)
    checked = 0
    matched = 0
    missing = 0
    misses = []
    for key in ("action_items", "decisions"):
        for idx, item in enumerate(prediction.get(key, []) or []):
            evidence = str(item.get("evidence") or "").strip()
            if not evidence:
                missing += 1
                continue
            checked += 1
            match = _evidence_match(evidence, normalized_transcript)
            if match["matched"]:
                matched += 1
            else:
                misses.append({"type": key, "index": idx, "evidence": evidence, **match})
    total = checked + missing
    score = matched / total if total else 1.0
    return _clamp(score), {
        "checked": checked,
        "matched": matched,
        "missing": missing,
        "misses": misses,
    }


def _case_requires_evidence(gold):
    for key in ("action_items", "decisions"):
        for item in gold.get(key, []) or []:
            if str(item.get("evidence") or "").strip():
                return True
    return False


def _task_similarity(left, right, alias_map):
    left_norm = _normalize_text(left, alias_map)
    right_norm = _normalize_text(right, alias_map)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm in right_norm or right_norm in left_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _normalize_text(value, alias_map):
    text = str(value or "")
    for alias, canonical in sorted(alias_map.items(), key=lambda item: len(item[0]), reverse=True):
        if alias:
            text = text.replace(alias, canonical)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.lower())


def _normalize_evidence(value):
    return re.sub(r"\s+", "", str(value or ""))


def _evidence_match(evidence, normalized_transcript):
    normalized = _normalize_evidence(evidence)
    if not normalized:
        return {"matched": False, "matched_by": "empty", "match_score": 0.0}
    if normalized in normalized_transcript:
        return {"matched": True, "matched_by": "substring", "match_score": 1.0}
    tokens = _evidence_tokens(evidence)
    if not tokens:
        return {"matched": False, "matched_by": "tokens", "match_score": 0.0}
    overlap = [token for token in tokens if _token_in_text(token, normalized_transcript)]
    score = len(overlap) / len(tokens)
    return {
        "matched": score >= 0.5,
        "matched_by": "token_overlap",
        "match_score": _clamp(score),
    }


def _evidence_tokens(value):
    text = str(value or "").lower()
    words = re.findall(r"[a-z0-9]+", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    tokens = [word for word in words if len(word) >= 3 and word not in _STOPWORDS]
    for chunk in cjk_chunks:
        tokens.extend(_cjk_ngrams(chunk))
    seen = set()
    out = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _token_in_text(token, text):
    return any(candidate and candidate in text for candidate in _token_variants(token))


def _token_variants(token):
    variants = {token}
    for suffix in ("ing", "ed", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            variants.add(token[: -len(suffix)])
    return variants


def _cjk_ngrams(text, size=2):
    if len(text) <= size:
        return [text]
    return [text[idx : idx + size] for idx in range(len(text) - size + 1)]


def _is_iso_date(value):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def _canonical_name(value, alias_map):
    text = str(value or "").strip()
    return alias_map.get(text, text)


def _f1(gold_values, predicted_values):
    if not gold_values:
        return None
    if not predicted_values:
        return 0.0
    overlap = len(gold_values & predicted_values)
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted_values)
    recall = overlap / len(gold_values)
    return _clamp(2 * precision * recall / (precision + recall))


def _overall(scores):
    weights = {
        "participants": 0.2,
        "key_points": 0.25,
        "action_items": 0.3,
        "decisions": 0.25,
    }
    weighted = [
        scores.get(key, 0.0) * weight
        for key, weight in weights.items()
        if scores.get(key) is not None
    ]
    total_weight = sum(weight for key, weight in weights.items() if scores.get(key) is not None)
    if not total_weight:
        return 0.0
    return _clamp(sum(weighted) / total_weight)


def _clamp(value):
    return max(0.0, min(1.0, float(value)))
