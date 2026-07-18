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
3. Run the workspace flow.
4. Show the `V1 vs V2` panel.
5. Show the `Readable Minutes` view.
6. Show `Derived Tasks`.
7. Show `Cross-meeting Signals`.
8. Switch to `Benchmark` to prove the architecture is also measurable.

## What To Say On Each Screen

### Workbench Input

Key point:

`Minsight` accepts either a pasted transcript or a reusable mock case. This makes the demo work both as a product story and as an engineering validation surface.

### V1 vs V2

Key point:

`V1` is a fragile single-call baseline. `V2` keeps the same target schema, but adds staged extraction, validation, repair, and evidence-bearing output.

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

This is still measurable. The product demo does not replace engineering evaluation; it sits on top of it.

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
- V1 vs V2 comparison
- readable minutes
- evidence display
- derived tasks
- duplicate-task and decision-reversal alerts

Not implemented yet:

- real downstream task push
- human review write-back
- semantic duplicate detection
- full dashboard analytics
