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
- Segment map calls run concurrently through a shared `ThreadPoolExecutor`
  helper. The workflow preserves input segment order before dedupe/reduce, so
  concurrency improves latency without changing result ordering semantics.
- `MINSIGHT_SEGMENT_WORKERS` controls per-agent segment concurrency and defaults
  to `4`.
- `KeyPointsReduceAgent` performs meeting-level compression when segment-level
  candidates exceed the desired final range. It removes off-topic chatter and
  merges fragmented process notes into business topics.
- `DecisionFilterAgent` filters candidate decisions to topic-level final
  decisions, removing clarifications, process discussion, implementation notes,
  and duplicates.
- `NormalizeAgent` still reads the full transcript so participant and alias
  extraction stays global.

The LangGraph flow is now:

```text
segment -> normalize -> key_points/actions_decisions -> key_points_reduce/decision_filter -> validate
```

## Consequences

- Long meetings get better recall opportunities because each segment has a
  smaller context window.
- Short meetings keep the previous cost profile.
- Roster and meeting-date context remain first-class inputs for nickname and
  relative-date handling.
- Candidate dedupe remains deterministic, while final key-point reduce and
  decision filtering use focused LLM calls. This keeps recall and precision as
  separate workflow responsibilities.
- Benchmark runs are faster on long scenarios because segment extraction can
  overlap remote LLM latency. Very high values for `MINSIGHT_SEGMENT_WORKERS`
  may hit provider rate limits, so the default stays conservative.
- Decision filtering directly targets benchmark failures where clarification
  statements, implementation details, or repeated process discussion were
  incorrectly reported as final decisions.

## Follow-Ups

- Add a long-meeting-only verify pass for missing topic-level decisions.
- Add segment relevance gating for real transcripts with heavy off-topic
  sections.
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
