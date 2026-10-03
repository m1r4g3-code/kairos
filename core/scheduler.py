"""
KAIROS core — a job loop for a PC that is not always on.

Each job decides from the clock and the saved state whether it is due, then
runs. Nothing depends on the loop having run continuously: a job that finds
work it missed while the PC was off either catches up (settling) or skips it
(a betting window that has passed). Every job writes its own state through
core.store, so the loop can be killed between or during jobs.

    loop = Loop(jobs, health_path, stop_path)
    loop.run_forever(sleep_s=300)     # or loop.tick() once

A job is any object with `name`, `due(now) -> bool` and `run(now) -> str`.
An exception in one job is logged to the health file and does not stop the
others. Creating the stop file ends the loop at the next tick.

Pure stdlib. Nothing here knows about football.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
import traceback


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Health:
    """Append-only health log: one JSON line per event."""

    def __init__(self, path: str):
        self.path = path

    def write(self, level: str, what: str, detail: str = "", now: dt.datetime | None = None) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        rec = {"utc": (now or utcnow()).isoformat(timespec="seconds"), "level": level,
               "what": what, "detail": detail[:2000]}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    def tail(self, n: int = 50) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as f:
                lines = f.readlines()[-n:]
        except FileNotFoundError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


class Loop:
    def __init__(self, jobs: list, health_path: str, stop_path: str, clock=utcnow):
        self.jobs, self.health, self.stop_path, self.clock = jobs, Health(health_path), stop_path, clock

    def tick(self) -> list[tuple[str, str]]:
        """Run every due job once. Returns (job name, outcome) pairs."""
        done = []
        for job in self.jobs:
            now = self.clock()
            try:
                if not job.due(now):
                    continue
                msg = job.run(now) or "ok"
                self.health.write("info", job.name, msg, now)
                done.append((job.name, msg))
            except Exception as e:          # one failing job must not stop the rest
                self.health.write("error", job.name,
                                  f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}", now)
                done.append((job.name, f"error: {e}"))
        return done

    def stop_requested(self) -> bool:
        return os.path.exists(self.stop_path)

    def run_forever(self, sleep_s: int = 300) -> None:
        self.health.write("info", "loop", "started")
        try:
            while not self.stop_requested():
                self.tick()
                for _ in range(max(1, sleep_s // 5)):          # wake every 5 s to notice a stop
                    if self.stop_requested():
                        break
                    time.sleep(5)
        finally:
            self.health.write("info", "loop", "stopped")
            try:
                os.remove(self.stop_path)
            except FileNotFoundError:
                pass
