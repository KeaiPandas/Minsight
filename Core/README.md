# Minsight Core

`Core/` contains the extraction engines only.

- `v1/`
  Archived single-call baseline. Kept for reference, no longer part of the active Lab benchmark flow.
- `v2/`
  The formal Minsight Agent, built as a LangGraph workflow from explicit agents.
- `shared/`
  Prompt rendering, schema validation, model routing, and scenario loading
- `data/scenarios/`
  Mock cases and gold data reused by `Lab/`

`Core/` no longer owns evaluation or demo orchestration. Those product-facing flows live in [Lab](/D:/Interview/Minsight/Lab/README.md):

- `Benchmark`
  Regression evaluation for the formal Minsight Agent across benchmark runs
- `Workbench`
  Business-facing meeting demo with readable minutes, evidence, tasks, and alerts

External integrations also live in Lab. For example, `derived_tasks -> Feishu
Tasks` sync is implemented as a Lab integration sink, so Core stays independent
from Feishu auth, CLI, and API concerns.

## Quick Start

Configure at least one OpenAI-compatible model profile in `.env`, then run:

```bash
pip install -r requirements.txt
python run.py --version v2 --scenario decision_reversal
python v2/run.py --scenario missing_fields
```

## Model Routing

Core keeps the three routing tiers:

- `light`
  normalization and repair
- `standard`
  key points
- `strong`
  actions, decisions, and Lab judge

Each agent resolves its model profile through `.env` using `AGENT_<NAME>=<profile>`.

## Scenario Fixtures

`Core/data/scenarios/*.json` is the shared benchmark source of truth.
Each file contains one complex meeting case with:

- `transcript`
- `meeting_info`
- `complexity_tags`
- `gold`

Gold annotations follow [annotation_rubric.md](/D:/Interview/Minsight/docs/annotation_rubric.md).

Current scenarios:

| Scenario | Purpose |
|---|---|
| `decision_reversal` | Final decision supersedes an earlier decision. |
| `long_meeting` | Long context, exclusions, late corrections, and multiple outputs. |
| `missing_fields` | Missing or implicit owner/due fields without hallucination. |
| `mixed_language` | Chinese-English mixed product discussion. |
| `multi_topic` | Mixed agenda items, parking-lot topics, and non-decisions. |
| `nickname_reference` | Nickname resolution and internal-owner assignment. |
| `real_world_kickoff` | Long real-world kickoff discussion with prioritization and scope cuts. |

Lab uses these fixtures to run Minsight Agent regression comparisons across runs.
The workbench can also load them as demo cases.
