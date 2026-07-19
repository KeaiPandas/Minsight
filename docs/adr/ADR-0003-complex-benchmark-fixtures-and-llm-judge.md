# ADR-0003: Use Complex Fixtures And LLM Judge For Lab Benchmark

- Date: 2026-07-18
- Status: Accepted

## Context

The early benchmark fixtures were too clean and topic-separated.
That made the workflow easier than the real problem: meetings often contain side topics, corrections, nickname references, non-decisions, already-completed work, and ambiguous owners or dates.

Semantic-similarity scoring was considered, but it would require another external embedding or similarity model API.
For the current demo and iteration loop, that adds cost and operational complexity without improving the story enough.

## Decision

Keep six benchmark scenario files under `Core/data/scenarios/`, but make each one intentionally harder and focused on a different capability:

| Scenario | Evaluation Focus |
|---|---|
| `decision_reversal` | Final decision versus superseded earlier decision. |
| `long_meeting` | Long context, exclusions, late correction, multiple outputs. |
| `missing_fields` | Missing or implicit owner/due fields without hallucination. |
| `mixed_language` | Chinese-English mixed terminology and scoped decisions. |
| `multi_topic` | Mixed agenda items, parking-lot topics, and non-decisions. |
| `nickname_reference` | Nickname resolution and internal-owner assignment. |

Each case should include:

- a realistic transcript of at least moderate length
- `complexity_tags`
- a human-authored `gold` answer
- enough participants, key points, action items, and decisions to exercise V1/V2 differences

Lab uses LLM judge as the only semantic scoring mechanism for now.

## Consequences

- Benchmark scores are easier to explain: V1/V2 output is compared against human-authored `gold`.
- Scores are dimension-level decimals from `0.0` to `1.0`, rendered as percentages in the frontend.
- Results may have small judge-model variance, so they are best used for iteration direction and regression review rather than as a mathematically deterministic metric.
- Rule-based or hybrid metrics can be added later behind the Lab judgement seam without changing Core.

## Validation

`Lab/tests/test_scenarios.py` protects fixture quality by checking that loaded benchmark cases are non-trivial and contain enough gold structure for evaluation.
