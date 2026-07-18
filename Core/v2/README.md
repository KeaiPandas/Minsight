# V2 Structured Extraction

V2 is the active Minsight extraction workflow. It uses LangGraph to orchestrate
small agents and produces the final structured meeting-minutes JSON.

## Agents

- `segment_agent.py`: deterministic long-transcript segmentation.
- `normalize_agent.py`: participants and alias map.
- `key_points_agent.py`: segment-level key-point extraction plus reduce.
- `actions_decisions_agent.py`: segment-level action/decision extraction plus
  reduce, with roster/date context.
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
- `meeting_info.attendees` and `meeting_info.date` are first-class inputs for
  nickname normalization and relative-date normalization.
