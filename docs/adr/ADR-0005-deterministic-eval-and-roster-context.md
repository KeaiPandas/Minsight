# ADR-0005: Use Deterministic Evaluation And Roster Context

- Date: 2026-07-18
- Status: Accepted

## Context

The `nickname_reference` benchmark exposed two separate problems:

- Participant and owner scores were unstable when judged entirely by LLM judge, even when the predicted names were nearly identical across runs.
- The V2 workflow was asking the normalize agent to infer real names from transcript text alone, while realistic products usually have meeting metadata from calendar or meeting systems: date plus attendee account/display/name/role information.

Objective dimensions such as participant names, action owners, due dates, and basic format validity should not depend on black-box judge variance.

## Decision

Split benchmark scoring into two layers:

- Deterministic objective metrics in `Lab/metrics.py` score `participants` and `action_items`.
- LLM judge remains responsible for semantic dimensions, especially `key_points` and `decisions`.

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
- Judge prompt remains compatible with the existing response schema, but its participants/action scores are only references and are overwritten by deterministic metrics when gold data exists.

## Validation

Covered by:

- `Lab/tests/test_metrics.py`
- `Lab/tests/test_runtime.py`
- `Lab/tests/test_prompts.py`

Run:

```powershell
python -m unittest discover -s Lab\tests -v
```
