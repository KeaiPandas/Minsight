# V2 Structured Extraction

V2 is the active Minsight extraction workflow. It uses LangGraph to orchestrate
small agents and produces the final structured meeting-minutes JSON.

## Agents

- `segment_agent.py`: deterministic long-transcript segmentation.
- `normalize_agent.py`: participants and alias map.
- `key_points_agent.py`: segment-level key-point extraction and candidate dedupe.
- `key_points_reduce_agent.py`: meeting-level key-point compression for noisy
  long-meeting candidates.
- `actions_decisions_agent.py`: segment-level action/decision extraction plus
  candidate dedupe, with roster/date context.
- `decision_filter_agent.py`: final decision filtering that drops
  clarifications, process notes, implementation details, and duplicates.
- `repair_agent.py`: one repair pass for malformed structured outputs.
- `validation_agent.py`: local final-shape validation and owner normalization.

## Run

From `D:\Interview\Minsight\Core`:

```powershell
python v2\run.py --scenario decision_reversal
```

The real LLM profiles must be configured in `Core\.env`, repository `.env`, or
`Lab\.env`.

## Notes

- Short transcripts still run as a single segment.
- Long transcripts are split into ordered windows before key-point and
  action/decision extraction.
- Segment-level key-point and action/decision map calls run concurrently.
  Tune `MINSIGHT_SEGMENT_WORKERS` to trade speed for API rate-limit safety
  (default: `4`).
- Key-point reduce and decision filtering are separate convergence steps, so
  recall and precision can be tuned independently.
- `meeting_info.attendees` and `meeting_info.date` are first-class inputs for
  nickname normalization and relative-date normalization.
