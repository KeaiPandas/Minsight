# ADR-0002: Lab Owns Benchmark Runtime And Storage Seams

- Date: 2026-07-17
- Status: Accepted

## Context

Lab exists to benchmark Core extractors, but reliability problems appear when execution flow, HTTP serving, persistence, and extractor selection are mixed together without clear seams.

## Decision

Lab owns three public seams:

1. HTTP benchmark control surface
2. Benchmark orchestration surface
3. Benchmark persistence surface

Core remains responsible only for extraction behavior and shared model/config utilities.

## Consequences

- Lab should not depend on removed or internal Core orchestration files.
- Tests should target Lab seams instead of Lab internals.
- Future storage replacements should happen behind the Lab store seam.

## 2026-07-18 Update

Lab now owns two user-facing flows:

1. `Benchmark`
   Runs V1 and V2 against the shared scenario set, stores predictions, then scores stored predictions with LLM judge.
2. `Workbench`
   Runs a transcript or mock case through V2 only, persists meeting assets, and renders readable minutes, evidence, derived tasks, and cross-meeting alerts.

Benchmark cases remain in `Core/data/scenarios/*.json` because they are shared extractor inputs.
The evaluation lifecycle remains in Lab because scoring, persistence, run archive, deletion, and UI reporting are product/test surfaces rather than extractor behavior.

The benchmark percentage shown in Lab is the average of stored LLM-judge scores.
It is not a semantic-similarity score and does not call an embedding model.
