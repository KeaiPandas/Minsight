# ADR-0004: Standardize V2 Prompt Quality

- Date: 2026-07-18
- Status: Accepted

## Context

Minsight V2 is now the active product workflow. The previous prompts could run, but they were too implicit: role definition, extraction rules, failure boundaries, and expected JSON shapes were scattered or missing.

That made benchmark iteration noisy. When a score changed, it was hard to tell whether the agent improved because of workflow design, model behavior, or accidental prompt interpretation.

## Decision

Standardize every V2 prompt around the same contract:

- `System / role`: define the specialist role of the current agent.
- `Task`: state the exact extraction or repair job.
- `Internal analysis steps`: guide the model to reason step by step internally, without outputting chain-of-thought.
- `Rules`: make boundaries explicit, including JSON-only output, no hallucinated facts, and evidence requirements.
- `Few-shot`: include a small example that demonstrates the expected output shape.

The updated prompt files are:

- `Core/prompts/v2/normalize.txt`
- `Core/prompts/v2/key_points.txt`
- `Core/prompts/v2/actions_decisions.txt`
- `Core/prompts/v2/repair.txt`

The V2 agents should continue returning only structured JSON. Reasoning traces stay internal and are not part of persisted results.

## Consequences

- Benchmark changes should be easier to attribute because prompt structure is now consistent across agents.
- The action and decision agent has stricter rules for owners, due dates, superseded decisions, and evidence snippets.
- The repair agent is constrained to schema/JSON repair only, so it should not invent new meeting facts during recovery.
- Future prompt edits should preserve this structure unless there is a specific ADR-level reason to change it.

## Validation

`Lab/tests/test_prompts.py` checks that each V2 prompt includes role, internal steps, rules, few-shot examples, JSON-only constraints, and required placeholders.

Run:

```powershell
python -m unittest Lab.tests.test_prompts -v
```
