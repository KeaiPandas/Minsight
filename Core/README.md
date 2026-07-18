# Minsight Core

`Core/` contains the extraction engines only.

- `v1/`
  Single-call baseline
- `v2/`
  LangGraph workflow built from explicit agents
- `shared/`
  Prompt rendering, schema validation, model routing, and scenario loading
- `data/scenarios/`
  Mock cases and gold data reused by `Lab/`

`Core/` no longer owns evaluation or demo orchestration. Those product-facing flows live in [Lab](/D:/Interview/Minsight/Lab/README.md):

- `Benchmark`
  Version-vs-version evaluation
- `Workbench`
  Business-facing meeting demo with readable minutes, evidence, tasks, and alerts

## Quick Start

Configure at least one OpenAI-compatible model profile in `.env`, then run:

```bash
pip install -r requirements.txt
python run.py --version v2 --scenario decision_reversal
python run.py --version v1 --scenario decision_reversal
python v2/run.py --scenario missing_fields
python v1/run.py --scenario missing_fields
```

## Model Routing

Core keeps the three routing tiers:

- `light`
  normalization and repair
- `standard`
  key points
- `strong`
  actions, decisions, V1 baseline, and Lab judge

Each agent resolves its model profile through `.env` using `AGENT_<NAME>=<profile>`.
