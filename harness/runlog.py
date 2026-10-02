"""
KAIROS harness — run log. Every variant that is run gets one line in
research/runs.jsonl, whether it worked or not. Lines are never removed.

Pure stdlib.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "research", "runs.jsonl")


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "harness", "engine"],
                               cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def append(hypothesis: str, variant: str, scope: str, result: dict, path: str = RUNS) -> dict:
    rec = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "commit": git_commit(), "hypothesis": hypothesis, "variant": variant,
           "scope": scope, "result": result}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec
