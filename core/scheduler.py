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

A network failure (no connection, DNS failure, reset, timeout) is not a bug in
the job: it is logged once as a warning when it starts and once when the job
next gets through, however many ticks fail in between. While any job is
offline the loop retries every `retry_s` seconds instead of waiting a full
sleep, and when the PC comes back from sleep (the clock jumps) it ticks at once.

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


def is_offline(e: BaseException) -> bool:
    """True for a failure to reach a server at all; an HTTP error status is not one."""
    if hasattr(e, "code"):                       # urllib.error.HTTPError: the server answered
        return False
    return isinstance(e, (OSError, TimeoutError))    # URLError, socket and ssl errors are OSErrors


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
        self.heartbeat_path = os.path.join(os.path.dirname(health_path) or ".", "heartbeat.txt")
        self._down: dict = {}          # job name -> [first failure time, failed ticks]

    def beat(self) -> None:
        """Record that the loop is alive, even when no job had anything to do."""
        tmp = self.heartbeat_path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(self.clock().isoformat(timespec="seconds"))
        os.replace(tmp, self.heartbeat_path)

    def tick(self) -> list[tuple[str, str]]:
        """Run every due job once. Returns (job name, outcome) pairs."""
        self.beat()
        done = []
        for job in self.jobs:
            now = self.clock()
            try:
                due = job.due(now)
                msg = (job.run(now) or "ok") if due else None
            except Exception as e:          # one failing job must not stop the rest
                if is_offline(e):
                    seen = self._down.setdefault(job.name, [now, 0])
                    seen[1] += 1
                    if seen[1] == 1:
                        self.health.write("warn", job.name, f"offline: {type(e).__name__}: {e}"[:300], now)
                    done.append((job.name, f"offline: {e}"))
                else:
                    self.health.write("error", job.name,
                                      f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}", now)
                    done.append((job.name, f"error: {e}"))
                continue
            was_down = self._down.pop(job.name, None)
            if was_down:
                self.health.write("info", job.name, f"back online after {was_down[1]} failed "
                                  f"tries since {was_down[0].isoformat(timespec='seconds')}", now)
            if msg is not None:
                self.health.write("info", job.name, msg, now)
                done.append((job.name, msg))
        return done

    def stop_requested(self) -> bool:
        return os.path.exists(self.stop_path)

    def run_forever(self, sleep_s: int = 300, retry_s: int = 60, step_s: float = 5,
                    wall=time.time, nap=time.sleep) -> None:
        self.health.write("info", "loop", "started")
        try:
            while not self.stop_requested():
                self.tick()
                wait = min(sleep_s, retry_s) if self._down else sleep_s
                for _ in range(max(1, int(wait // step_s))):   # wake every few seconds to notice a stop
                    if self.stop_requested():
                        break
                    before = wall()
                    nap(step_s)
                    gap = wall() - before
                    if gap > step_s + 60:                      # the PC was asleep: catch up now
                        self.health.write("info", "loop", f"resumed after {gap / 60:.0f} minutes asleep")
                        nap(min(20, step_s * 4))               # give the network a moment to reconnect
                        break
        finally:
            self.health.write("info", "loop", "stopped")
            try:
                os.remove(self.stop_path)
            except FileNotFoundError:
                pass
