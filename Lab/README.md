# Minsight Lab

`Lab/` now serves two purposes:

1. `Benchmark`
   Run V1 and V2 against the shared scenario set, persist predictions, and score them with the LLM judge.
2. `Workbench`
   Run a real transcript or mock case through V1 and V2, persist meeting assets, show readable minutes, evidence, derived tasks, and cross-meeting alerts.

## Public Seams

The Lab critical path is organized around three public seams:

1. `HTTP API`
   Exposed by [server.py](/D:/Interview/Minsight/Lab/server.py)
2. `Runtime`
   Owned by [runtime.py](/D:/Interview/Minsight/Lab/runtime.py)
3. `SQLite store`
   Implemented by [store.py](/D:/Interview/Minsight/Lab/store.py)

Supporting modules:

- [judge.py](/D:/Interview/Minsight/Lab/judge.py)
  LLM judge for benchmark scoring
- [web/](/D:/Interview/Minsight/Lab/web)
  Static frontend for both workbench and benchmark views

## What The Workbench Adds

The workbench demo closes the business loop that the benchmark view does not:

- transcript input or mock case selection
- direct V2 execution with side-by-side V1 comparison
- human-readable meeting minutes
- evidence display for action items and decisions
- `action_items -> derived_tasks` persistence
- cross-meeting duplicate-task hints

SQLite now stores lightweight business assets in addition to benchmark records:

- `meetings`
- `meeting_actions`
- `meeting_decisions`
- `derived_tasks`

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the web console:

```bash
python server.py
```

Then open:

```text
http://127.0.0.1:8787
```

The default landing tab is `Workbench`. The second tab is `Benchmark`.

You can still run benchmark-only CLI mode:

```bash
python run.py --scenario decision_reversal
```

## API Surface

Benchmark APIs:

- `GET /api/scenarios`
- `GET /api/runs`
- `POST /api/run`
- `GET /api/run?id=<run_id>`
- `DELETE /api/run?id=<run_id>`

Workbench APIs:

- `GET /api/demo/cases`
- `GET /api/demo/meetings`
- `POST /api/demo/run`
- `GET /api/demo/meeting?id=<meeting_id>`

## Outputs

SQLite file:

- `minsight_lab.sqlite`
  Benchmark records plus workbench meeting assets

Benchmark artifacts:

- `results/<run_id>.json`
  Aggregated benchmark summary for a completed run

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```

The automated coverage now protects:

- benchmark store persistence
- benchmark runtime lifecycle
- workbench meeting asset persistence
- benchmark HTTP flow
- workbench HTTP flow
