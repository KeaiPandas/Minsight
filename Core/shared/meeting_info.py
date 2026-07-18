# -*- coding: utf-8 -*-
"""Utilities for realistic meeting context.

`meeting_info` represents data available before extraction, such as calendar
date and attendee account/display information. It is not a gold alias map.
"""

import json


def get_meeting_info(case):
    return case.get("meeting_info") or {}


def get_meeting_date(case):
    meeting_info = get_meeting_info(case)
    return meeting_info.get("date") or case.get("meeting_date") or "unknown"


def build_roster_aliases(meeting_info):
    aliases = {}
    for attendee in meeting_info.get("attendees", []) or []:
        canonical = (attendee.get("name") or attendee.get("account") or attendee.get("display_name") or "").strip()
        if not canonical:
            continue
        for key in ("name", "display_name", "account"):
            value = (attendee.get(key) or "").strip()
            if value:
                aliases[value] = canonical
        for value in attendee.get("aliases", []) or []:
            value = str(value).strip()
            if value:
                aliases[value] = canonical
    return aliases


def render_meeting_info(case):
    return json.dumps(get_meeting_info(case), ensure_ascii=False, indent=2)
