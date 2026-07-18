# ADR-0006: Add Segment Map-Reduce To V2 Extraction

- Date: 2026-07-18
- Status: Accepted

## Context

V2 originally ran each extraction agent over the full transcript in a single call.
That worked for short meetings, but long and noisy meetings exposed two recurring
risks:

- Key points became too coarse because one call had to summarize too many topics.
- Action items and decisions could be missed when important statements were far
  apart in a long transcript.

The benchmark now includes long, mixed-topic, ASR-noisy cases, so the workflow
needs a stronger long-meeting path without doubling cost for every short meeting.

## Decision

Add deterministic segmentation before extraction:

- `SegmentAgent` splits long transcripts into ordered line windows with small
  overlap and uses no LLM call.
- Short transcripts are passed through as a single segment.
- `KeyPointsAgent.run_many()` maps over segments and reduces duplicate
  topic/summary pairs.
- `ActionsDecisionsAgent.run_many()` maps over segments while injecting the
  alias map and meeting date into every call, then reduces duplicate actions and
  decisions.
- `NormalizeAgent` still reads the full transcript so participant and alias
  extraction stays global.

The LangGraph flow is now:

```text
segment -> normalize -> key_points/actions_decisions -> validate
```

## Consequences

- Long meetings get better recall opportunities because each segment has a
  smaller context window.
- Short meetings keep the previous cost profile.
- Roster and meeting-date context remain first-class inputs for nickname and
  relative-date handling.
- Reduce logic is intentionally simple and deterministic. If later benchmark
  runs show over-merging or under-merging, that reducer can evolve behind the
  same `run_many()` seam.

## Follow-Ups

- Add a long-meeting-only verify pass for missing topic-level decisions.
- Consider a two-step decision extractor: recall candidate decisions first, then
  filter with the annotation rubric.
- Expose segment-level routing/traces in Lab only if it helps debugging without
  cluttering the demo.

## Validation

Covered by:

- `Lab/tests/test_v2_workflow.py`
- `Lab/tests/test_runtime.py`

Run:

```powershell
python -m unittest D:\Interview\Minsight\Lab\tests\test_v2_workflow.py D:\Interview\Minsight\Lab\tests\test_runtime.py -v
```
