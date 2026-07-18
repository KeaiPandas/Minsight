# -*- coding: utf-8 -*-

import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
