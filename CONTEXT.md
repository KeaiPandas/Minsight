# Minsight Context

## Product

Minsight is a meeting-minutes intelligence platform.

Its core flow is:

1. Ingest meeting transcripts from upstream producers.
2. Extract structured meeting data with LLM-based workflows.
3. Persist structured assets for cross-meeting retrieval and comparison.
4. Evaluate extractor quality through the standalone Lab benchmark project.

## Core Domain Terms

- `meeting`
  A single meeting input with transcript and metadata.
- `participant`
  A person identified in a meeting, optionally with a role.
- `key_point`
  A discussion topic or summary point extracted from a meeting.
- `action_item`
  A task extracted from a meeting, with owner and optional due date.
- `decision`
  A finalized or superseded meeting decision.
- `prediction`
  A structured extraction result produced by a benchmark variant.
- `judgement`
  An LLM-judge score object comparing a prediction with gold data.
- `benchmark_run`
  One complete Lab execution across one scenario or the full scenario set.

## Module Map

- `Core/`
  Production extraction code and prompts.
- `Core/v1/`
  Single-call baseline extractor.
- `Core/v2/`
  Multi-agent LangGraph extractor.
- `Lab/`
  Standalone benchmark runner, persistence layer, judge flow, and frontend console.
- `Deploy/`
  Production-facing workbench entrypoint. It exposes meeting extraction,
  readable minutes, evidence, derived tasks, decision sync, and health checks,
  but intentionally does not expose Lab benchmark APIs or benchmark UI.
- `PRD/`
  Product and design documents.

## Current Architecture Facts

- V2 no longer uses an offline or plain pipeline fallback.
- V2 is organized as explicit agents under `Core/v2/agents/`.
- `Core/v2/graph.py` is the only V2 orchestration entrypoint.
- Lab is decoupled from Core except for public extractor and shared scenario/model utilities.
- Lab runtime now owns benchmark lifecycle through `Lab/runtime.py`.
- Lab stores benchmark runs in SQLite by default.
- Deploy owns the first V4 production boundary through `Deploy/server.py`.
- Deploy runtime owns the production workbench lifecycle through
  `Deploy/runtime.py`.
- Deploy currently reuses Lab store/integrations as a bridge, while keeping Lab
  benchmark runtime, benchmark HTTP routes, and benchmark frontend out of the
  deployable surface.

## Current Public Seams

- `Lab HTTP API`
  Implemented by `Lab/server.py`
- `Lab benchmark runtime`
  Implemented by `Lab/runtime.py`
- `Lab SQLite store`
  Implemented by `Lab/store.py`
- `Deploy Workbench HTTP API`
  Implemented by `Deploy/server.py`
- `Deploy workbench runtime`
  Implemented by `Deploy/runtime.py`

## Current Status

- The stale `v2.pipeline` dependency has been removed from Lab.
- The frontend control path has been simplified to one benchmark mode.
- Automated tests now protect the three Lab public seams.
- Deploy has a separate V4 workbench-only entrypoint and tests that assert
  benchmark APIs are not exposed.

## Preferred Architectural Direction

- Keep Core focused on extraction seams.
- Keep Lab focused on evaluation seams.
- Keep Deploy focused on production workbench seams.
- Keep tests on public seams only:
  HTTP API, benchmark runtime, deploy runtime boundary, and persistence.
- Prefer deeper modules with fewer cross-file jumps on the critical path.
