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
- `ActionFilterAgent` filters action candidates after segment-level recall. It
  keeps formal assigned tasks and removes casual follow-ups, already-completed
  items, vague notes, and duplicate/near-duplicate tasks.
- Segment map calls run concurrently through a shared `ThreadPoolExecutor`
  helper. The workflow preserves input segment order before dedupe/reduce, so
  concurrency improves latency without changing result ordering semantics.
- `MINSIGHT_SEGMENT_WORKERS` controls per-agent segment concurrency and defaults
  to `2`.
- `MINSIGHT_BENCHMARK_WORKERS` controls Lab case-level prediction/judge
  concurrency and defaults to `2`.
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
segment -> normalize -> key_points/actions_decisions -> key_points_reduce/action_filter/decision_filter -> validate
```

## Consequences

- Long meetings get better recall opportunities because each segment has a
  smaller context window.
- Short meetings keep the previous cost profile.
- Roster and meeting-date context remain first-class inputs for nickname and
  relative-date handling.
- Candidate dedupe remains deterministic, while final key-point reduce and
  action/decision filtering use focused LLM calls. This keeps recall and
  precision as separate workflow responsibilities.
- Benchmark runs are faster on long scenarios because segment extraction can
  overlap remote LLM latency. Very high values for `MINSIGHT_SEGMENT_WORKERS`
  or `MINSIGHT_BENCHMARK_WORKERS` may hit provider rate limits, so the defaults
  stay conservative.
- Decision filtering directly targets benchmark failures where clarification
  statements, implementation details, or repeated process discussion were
  incorrectly reported as final decisions.
- Action filtering targets the `4ba29fdf` regression analysis: overall score
  fell mainly because action-item precision dropped across long/noisy cases,
  even while decision precision improved.

## Progress Updates

### 2026-07-18: Action Precision Hardening

Benchmark run `4ba29fdf` completed successfully but regressed overall score from
the previous comparable full run. The regression was concentrated in
`action_items`: decision quality improved, but noisy action extraction pulled the
weighted overall score down.

To address this, V2 now separates action recall from action precision:

- `ActionsDecisionsAgent` remains recall-oriented and extracts action/decision
  candidates from each segment.
- `ActionFilterAgent` performs a meeting-level convergence pass over action
  candidates.
- The filter keeps formal assigned future work and removes casual follow-ups,
  already-completed work, vague notes, rejected tasks, parking-lot items, and
  duplicates.

### 2026-07-18: Prompt Language Policy

The reduce/filter prompts now use a mixed prompt style:

- English instructions for role, rules, reasoning steps, and JSON constraints.
- Chinese few-shot examples, because the benchmark and target meeting
  transcripts are primarily Chinese.
- English JSON field names remain unchanged to preserve schema stability.

This policy avoids Windows encoding issues in instruction text while keeping the
examples close to production data distribution.

### 2026-07-18: Rate-Limit Guardrails

Benchmark run `ddd54612` showed that the new action filtering improved valid-case
quality, but two cases (`multi_01` and `real_01`) failed with provider 429
rate-limit errors. Those failures produced empty structured outputs and pulled
the aggregate score down, making infrastructure failures look like model-quality
regressions.

The workflow now adds three guardrails:

- Lower default concurrency from `4` to `2` for segment-level map calls.
- Lower Lab benchmark case-level prediction/judge concurrency to `2`.
- Retry transient LLM failures such as 429/rate-limit/timeout errors with
  exponential backoff.

Lab run details and result JSON now include `run_health`, which marks completed
but partially failed runs as `degraded` and lists failed cases by stage,
error type, and message. The Web summary card surfaces this state before the
score cards so reviewers can separate runtime reliability from extraction
quality.

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
