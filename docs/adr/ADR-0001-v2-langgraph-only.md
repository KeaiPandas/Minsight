# ADR-0001: V2 Uses LangGraph As The Only Orchestration Path

- Date: 2026-07-17
- Status: Accepted

## Context

V2 was previously split between a plain Python pipeline and a LangGraph workflow.
This created duplicate entrypoints and stale integrations when the V2 extractor evolved.

## Decision

V2 will use `Core/v2/graph.py` as the single orchestration path.
Agent responsibilities live under `Core/v2/agents/`.
No separate plain pipeline entrypoint is maintained.

## Consequences

- Lab and other callers must integrate with the LangGraph path only.
- V2 agent evolution happens in one place.
- Dead fallback imports become easier to detect.
