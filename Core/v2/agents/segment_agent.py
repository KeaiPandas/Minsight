# -*- coding: utf-8 -*-
"""Deterministic transcript segmentation for long-meeting map/reduce."""


class SegmentAgent:
    """Split long transcripts into ordered line windows without extra LLM cost."""

    name = "segment"

    def __init__(self, max_chars=2400, overlap_lines=2):
        self.max_chars = max_chars
        self.overlap_lines = overlap_lines

    def run(self, case):
        transcript = case["transcript"]
        if len(transcript) <= self.max_chars:
            return [self._segment("seg_001", transcript, 1, len(transcript.splitlines()) or 1)]

        lines = transcript.splitlines()
        segments = []
        current = []
        start_line = 1
        for line_no, line in enumerate(lines, start=1):
            candidate = "\n".join([*current, line]) if current else line
            if current and len(candidate) > self.max_chars:
                segments.append(
                    self._segment(
                        f"seg_{len(segments) + 1:03d}",
                        "\n".join(current),
                        start_line,
                        line_no - 1,
                    )
                )
                overlap = current[-self.overlap_lines :] if self.overlap_lines else []
                current = [*overlap, line]
                start_line = max(1, line_no - len(overlap))
            else:
                current.append(line)
        if current:
            segments.append(
                self._segment(
                    f"seg_{len(segments) + 1:03d}",
                    "\n".join(current),
                    start_line,
                    len(lines),
                )
            )
        return segments

    @staticmethod
    def _segment(segment_id, text, start_line, end_line):
        return {
            "segment_id": segment_id,
            "text": text,
            "start_line": start_line,
            "end_line": end_line,
        }
