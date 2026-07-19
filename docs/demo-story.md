# Minsight Demo Story

This document is the shortest path for presenting Minsight as a business demo instead of only a benchmark project.

## Demo Goal

Show that Minsight is not just:

- a V1 / V2 extractor comparison
- a benchmark harness

Show that it is:

- a meeting structuring workspace
- a store-first asset layer
- an action-derivation loop with evidence

## Demo Flow

1. Open the `Workbench` tab in Lab.
2. Load a mock case such as `rev_01 | decision_reversal`, or paste a custom transcript.
3. Run the V2 workspace flow.
4. Show the `Readable Minutes` view.
5. Show the V2 raw structured output.
6. Show `Derived Tasks`.
7. Show `Cross-meeting Signals`.
8. Switch to `Benchmark` to show whether the formal Agent improved or regressed compared with the previous run of the same case.

## What To Say On Each Screen

### Workbench Input

Key point:

`Minsight` accepts either a pasted transcript or a reusable mock case. This makes the demo work both as a product story and as an engineering validation surface.

### Readable Minutes

Key point:

The output is no longer raw JSON only. The same structured result is rendered into a human-readable meeting view with participants, key points, action items, and decisions.

### Evidence

Key point:

Every action item and decision can show the supporting source text, so the operator can verify where it came from.

### Derived Tasks

Key point:

The workflow does not stop at minutes. `action_items` are immediately transformed into `derived_tasks`, which is the minimum execution loop expected from a meeting middle platform.

### Cross-meeting Signals

Key point:

The system starts to accumulate reusable assets across meetings. Even a rule-based duplicate-task check already demonstrates the value of store-first architecture.

### Benchmark

Key point:

V1 is now archived. The benchmark focuses on current Agent regression: each run is compared against the previous run for the same scenario/case, so iteration gains and regressions are visible.

## Recommended Interview Script

Use this order:

1. product problem
2. why V1 breaks
3. what V2 changes
4. how results become assets and tasks
5. how the same system is benchmarked in Lab

## Current Scope

Implemented now:

- transcript or mock input
- V2-only workbench execution
- current Agent benchmark comparison against previous runs
- readable minutes
- raw V2 output inspection
- evidence display
- derived tasks
- duplicate-task and decision-reversal alerts
- complex benchmark fixtures with six scenario goals
- LLM-judge scoring shown as percentages in the Lab UI

Not implemented yet:

- real downstream task push
- human review write-back
- semantic duplicate detection
- full dashboard analytics

## Benchmark Story

The benchmark is not meant to prove that one static prompt is always better.
It is a regression surface for iterating the current agent workflow.

Current benchmark cases live in `Core/data/scenarios/*.json`.
Each case contains:

- `transcript`: the meeting script used as model input
- `complexity_tags`: why the case is hard
- `alias_map`: nickname or speaker-name normalization hints where relevant
- `gold`: the human-authored baseline answer

The six current scenarios intentionally test different failure modes:

| Scenario | Main Purpose |
|---|---|
| `decision_reversal` | Whether the extractor handles a final decision that supersedes an earlier decision. |
| `long_meeting` | Whether it survives longer context, exclusions, late corrections, and multiple decisions. |
| `missing_fields` | Whether it avoids hallucinating owners or due dates when information is implicit or missing. |
| `mixed_language` | Whether it handles Chinese-English code switching and product terms. |
| `multi_topic` | Whether it separates deployment, monitoring, reports, parking-lot items, and non-decisions. |
| `nickname_reference` | Whether it resolves nicknames and avoids assigning customer-side people as internal owners. |

## Score Explanation

Lab scores are produced by LLM judge, not by embedding similarity.

The flow is:

1. Run the formal Minsight Agent on the benchmark case.
2. Persist each prediction with `case_id`, `scenario`, `transcript`, `gold`, `output`, and routing metadata.
3. Send `transcript + gold + prediction` to the fixed judge prompt in `Lab/prompts/judge.txt`.
4. The judge returns decimal scores from `0.0` to `1.0` for `participants`, `key_points`, `action_items`, `decisions`, and `overall`.
5. The frontend renders those decimals as percentages.
6. For multi-case runs, Lab averages scores per variant and dimension.
7. If the same case has a previous Agent run, Lab returns current-minus-previous deltas for the frontend heatmap.

This makes the percentage easy to explain in interviews:
it is the strong model's dimension-level judgement of how close the prediction is to the human-authored gold answer.
