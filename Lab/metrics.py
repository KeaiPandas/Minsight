# -*- coding: utf-8 -*-
"""Deterministic objective metrics for benchmark scoring."""

from difflib import SequenceMatcher
import re

from shared.meeting_info import build_roster_aliases, get_meeting_info


def score_objective_dimensions(case, prediction):
    """Score objective dimensions that should not depend on LLM judge variance.

    Returns only dimensions that have enough gold data to score. Semantic
    dimensions such as key_points and decisions stay with the judge.
    """
    gold = case.get("gold", {})
    alias_map = build_roster_aliases(get_meeting_info(case))
    scores = {}

    if gold.get("participants"):
        scores["participants"] = _participant_score(
            gold.get("participants", []),
            prediction.get("participants", []),
            alias_map,
        )
    if gold.get("action_items"):
        scores["action_items"] = _action_item_score(
            gold.get("action_items", []),
            prediction.get("action_items", []),
            alias_map,
        )
    return scores


def combine_scores(semantic_scores, objective_scores):
    """Overlay deterministic scores onto semantic judge output."""
    result = dict(semantic_scores)
    for key, value in objective_scores.items():
        result[key] = value
    result["overall"] = _overall(result)
    return result


def _participant_score(gold_participants, predicted_participants, alias_map):
    gold_names = {_canonical_name(item.get("name"), alias_map) for item in gold_participants}
    predicted_names = {_canonical_name(item.get("name"), alias_map) for item in predicted_participants}
    gold_names.discard("")
    predicted_names.discard("")
    return _f1(gold_names, predicted_names)


def _action_item_score(gold_items, predicted_items, alias_map):
    if not gold_items:
        return None
    used = set()
    item_scores = []
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
            continue
        used.add(best_idx)
        predicted = predicted_items[best_idx]
        owner_ok = _canonical_name(gold.get("owner"), alias_map) == _canonical_name(predicted.get("owner"), alias_map)
        due_ok = (gold.get("due") or None) == (predicted.get("due") or None)
        item_scores.append((0.4 if best >= 0.35 else 0.0) + (0.35 if owner_ok else 0.0) + (0.25 if due_ok else 0.0))
    return _clamp(sum(item_scores) / len(item_scores))


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
