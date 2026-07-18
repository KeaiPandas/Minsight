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
