# Minsight Lab

`Lab/` now serves two purposes:

1. `Benchmark`
   Run the formal Minsight Agent against the shared scenario set, persist predictions, score them with the LLM judge, and compare each case with the previous run of the same task.
2. `Workbench`
   Run a real transcript or mock case through V2, persist meeting assets, show readable minutes, evidence, derived tasks, and cross-meeting alerts.

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
- direct V2 execution for the business-facing demo
- human-readable meeting minutes
- evidence display for action items and decisions
- `action_items -> derived_tasks` persistence
- cross-meeting duplicate-task hints

SQLite now stores lightweight business assets in addition to benchmark records:

- `meetings`
- `meeting_actions`
- `meeting_decisions`
- `derived_tasks`

## Benchmark Basis

Benchmark cases are loaded from `Core/data/scenarios/*.json`.
Each case has a human-authored `gold` answer for:

- `participants`
- `key_points`
- `action_items`
- `decisions`

The current six scenarios intentionally cover different failure modes:

| Scenario | Purpose |
|---|---|
| `decision_reversal` | Decision reversal and `supersedes`. |
| `long_meeting` | Long context and late corrections. |
| `missing_fields` | Missing owner/due fields and anti-hallucination. |
| `mixed_language` | Chinese-English mixed terms. |
| `multi_topic` | Topic switching and parking-lot filtering. |
| `nickname_reference` | Nickname/reference resolution. |

Scores shown in the UI come from LLM judge:

1. Lab runs the formal Minsight Agent on the selected case set.
2. Predictions and `gold` are persisted to SQLite.
3. `judge.py` sends `transcript + gold + prediction` to the fixed judge prompt.
4. The judge returns `0.0 ~ 1.0` scores for each dimension.
5. The frontend renders them as percentages.
6. If the same scenario/case has a previous V2 run, the frontend shows a heatmap of current score minus previous score.

No embedding similarity API is used in the current benchmark flow.

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
- scenario fixture complexity and gold coverage
