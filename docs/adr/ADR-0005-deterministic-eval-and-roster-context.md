# ADR-0005: Use Deterministic Evaluation And Roster Context

- Date: 2026-07-18
- Status: Accepted

## Context

The `nickname_reference` benchmark exposed two separate problems:

- Participant and owner scores were unstable when judged entirely by LLM judge, even when the predicted names were nearly identical across runs.
- The V2 workflow was asking the normalize agent to infer real names from transcript text alone, while realistic products usually have meeting metadata from calendar or meeting systems: date plus attendee account/display/name/role information.

Objective diagnostics such as participant names, action owners, due dates, evidence hints, and basic format validity should not depend on black-box judge variance. At the same time, rule checks should not dominate semantic quality scoring for action and decision extraction.

## Decision

Split benchmark scoring into two layers:

- Deterministic objective metrics in `Lab/metrics.py` score and explain objective signals.
- `participants` is the only dimension currently overridden by deterministic scoring, because roster/alias normalization is highly objective.
- `action_items`, `format_valid`, and `evidence` are persisted as diagnostic `_objective_scores` and `_objective_details`, but do not override LLM judge scores by default.
- LLM judge remains the primary scorer for semantic dimensions and action/decision quality.

Persist lightweight benchmark context with each prediction:

- `meeting_info.date`
- `meeting_info.attendees[]`

Use this context in both places:

- V2 normalize/actions prompts receive meeting metadata and meeting date context.
- Lab metrics derive normalization hints from `meeting_info.attendees` before comparing predictions with gold.

## Consequences

- Repeated scoring of the same prediction is stable for objective dimensions.
- Nickname-heavy cases can be evaluated against real names without treating a gold-style alias map as product input.
- The frontend score shape remains unchanged: `participants`, `key_points`, `action_items`, `decisions`, and `overall`.
- Judge prompt remains compatible with the existing response schema.
- Rule-based diagnostics are available in run details without making benchmark scores overly brittle.
- Judge JSON failures are captured as judgement rows with `_judge_error` instead of failing the whole benchmark run.

## Validation

Covered by:

- `Lab/tests/test_metrics.py`
- `Lab/tests/test_runtime.py`
- `Lab/tests/test_prompts.py`

Run:

```powershell
python -m unittest discover -s Lab\tests -v
```
