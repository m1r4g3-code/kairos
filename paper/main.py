"""
KAIROS paper trading — the one command.

    python paper/main.py            start the loop (stays running; one copy at a time)
    python paper/main.py --once     run every due job once and exit
    python paper/main.py --status   print the scorecard and the last health lines
    python paper/main.py --stop     ask a running loop to stop at its next tick

State lives in paper/state/. The loop can be killed at any moment; on restart it
settles what finished while it was off, skips betting windows it missed, and
carries on. Recommend-only: it places nothing and stores no bookmaker login.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs  # noqa: E402

from core.scheduler import Loop, utcnow  # noqa: E402
from core.store import SingleInstance    # noqa: E402

STATE = os.path.join(HERE, "state")
STOP = os.path.join(STATE, "STOP")


def load_config(path: str = os.path.join(HERE, "config.json")) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(cfg: dict, state_dir: str = STATE, **kw) -> tuple[jobs.Paper, Loop]:
    import power
    awake, wake = kw.pop("set_awake", power.set_awake), kw.pop("register_wake", power.register_wake)
    paper = jobs.Paper(cfg, state_dir, **kw)
    closing = jobs.Closing(paper)
    loop = Loop([power.KeepAwake(paper, closing, awake), jobs.Settle(paper), closing,
                 jobs.Snapshot(paper), power.Wake(paper, closing, wake),
                 jobs.Judge(paper), jobs.Scorecard(paper)],
                os.path.join(state_dir, "health.log"), os.path.join(state_dir, "STOP"))
    return paper, loop


def main(argv: list[str]) -> int:
    cfg = load_config()
    os.makedirs(STATE, exist_ok=True)
    if "--stop" in argv:
        open(STOP, "w").close()
        print("stop requested; the loop will exit within a few seconds")
        return 0
    paper, loop = build(cfg)
    if "--status" in argv:
        print(jobs.scorecard(paper, utcnow()))
        for h in paper.health.tail(10):
            print(f"{h['utc']} {h['level']:5} {h['what']}: {h['detail'][:120]}")
        return 0
    if not jobs.engine_config.ODDS_API_KEY:
        print("no Odds API key in .env (THE_ODDS_API_KEY or ODDS_API_KEY)")
        return 2
    try:
        with SingleInstance(os.path.join(STATE, "loop.lock")):
            if os.path.exists(STOP):
                os.remove(STOP)                   # a stale stop request from last time
            if "--once" in argv:
                for name, msg in loop.tick():
                    print(f"{name}: {msg}")
                return 0
            loop.run_forever(cfg["loop_sleep_seconds"], cfg.get("offline_retry_seconds", 60))
    except RuntimeError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
