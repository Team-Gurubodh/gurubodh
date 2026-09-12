"""Immutable #288 comparison inputs; never a production catalog or file loader."""
from copy import deepcopy
import json
from pathlib import Path

BASELINE = json.loads((Path(__file__).parent / "fixtures/maintained-jobs-stage-a.json").read_text())
CASES = BASELINE["jobs"]


def explicit_baseline(case):
    """Spell out retired representation allowances for in-memory regression tests.

    Exact raw differences are asserted separately before this adaptation.
    No values are obtained from the composer or current component catalog.
    """
    payload = deepcopy(case["configuration"])
    for side in ("source", "destination"):
        section = payload[side]
        section.setdefault("backend", "local")
        if section["backend"] == "r2":
            section.setdefault("url_base", None)
    split = payload.get("chapter_split", {})
    if split.get("pattern_type") == "regex":
        split.setdefault("flags", [])
    return payload


def baseline_job(command):
    case = next(c for c in CASES if c["selectors"]["command"] == command
                and c["selectors"]["storage_profile"] == "local")
    return explicit_baseline(case)
