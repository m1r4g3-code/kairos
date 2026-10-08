"""
KAIROS paper trading — keeping the PC available for closing prices.

A Pinnacle closing price can only be fetched in the hour before kickoff, so a
PC that dozes off then loses the pick's CLV. Two jobs, both Windows-only and
both harmless elsewhere:

  KeepAwake  While a match with a pick (or a census price) is inside its
             closing window, ask Windows not to go to sleep from idleness.
             Closing the lid or pressing the power button still sleeps it.
             On by default ("keep_awake_for_close").

  Wake       Register a one-off Task Scheduler task that wakes the PC from
             sleep shortly before the next closing window. OFF by default
             ("wake_for_close"): it can wake a laptop that is shut in a bag.

Neither places anything or touches any account. Pure stdlib.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys

from jobs import iso, parse_time

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
WAKE_TASK = "KairosPaperWake"


def set_awake(on: bool) -> bool:
    """Ask Windows to stay awake (or stop asking). True if the request was made."""
    if sys.platform != "win32":
        return False
    import ctypes
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
    return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))


def register_wake(local_time: dt.datetime, runner=subprocess.run) -> tuple[bool, str]:
    """Create or replace the one-off wake task. Returns (ok, detail)."""
    if sys.platform != "win32":
        return False, "not Windows"
    at = local_time.strftime("%Y-%m-%dT%H:%M:%S")
    ps = (f"$a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c exit'; "
          f"$t = New-ScheduledTaskTrigger -Once -At ([datetime]'{at}'); "
          f"$s = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
          f"Register-ScheduledTask -TaskName {WAKE_TASK} -Action $a -Trigger $t -Settings $s "
          f"-Description 'Kairos: wake for a closing price (recommend-only, no money)' -Force | Out-Null")
    try:
        r = runner(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"{type(e).__name__}: {e}"
    return r.returncode == 0, (r.stderr or r.stdout or "").strip()[:200]


def kickoffs_owed(paper, closing, now: dt.datetime) -> list[dt.datetime]:
    """Kickoff times, still ahead, of matches that need a closing price."""
    times = [p["commence"] for p in paper.open_picks(now)]
    times += [r["commence"] for r in closing._census_open(now)]
    return sorted({parse_time(t) for t in times if parse_time(t) > now})


class KeepAwake:
    name = "keep-awake"

    def __init__(self, paper, closing, setter=set_awake):
        self.p, self.closing, self.setter, self.on = paper, closing, setter, False

    def _want(self, now: dt.datetime) -> bool:
        if not self.p.cfg.get("keep_awake_for_close", True):
            return False
        lead = dt.timedelta(minutes=self.p.cfg.get("keep_awake_lead_minutes", 90))
        return any(k - lead <= now for k in kickoffs_owed(self.p, self.closing, now))

    def due(self, now: dt.datetime) -> bool:
        return self._want(now) != self.on

    def run(self, now: dt.datetime) -> str:
        want = self._want(now)
        ok = self.setter(want)
        self.on = want
        if want:
            return ("asked Windows to stay awake until the closing price is in" if ok
                    else "could not ask Windows to stay awake (not Windows, or refused)")
        return "no closing price due: normal sleep allowed again"


class Wake:
    name = "wake"

    def __init__(self, paper, closing, register=register_wake):
        self.p, self.closing, self.register = paper, closing, register

    def _target(self, now: dt.datetime) -> dt.datetime | None:
        if not self.p.cfg.get("wake_for_close", False):
            return None
        lead = dt.timedelta(minutes=self.p.cfg.get("wake_lead_minutes", 40))
        ahead = [k - lead for k in kickoffs_owed(self.p, self.closing, now)
                 if k - lead > now + dt.timedelta(minutes=2)]
        return min(ahead) if ahead else None

    def due(self, now: dt.datetime) -> bool:
        t = self._target(now)
        return t is not None and iso(t) != self.p.state().get("wake_at")

    def run(self, now: dt.datetime) -> str:
        t = self._target(now)
        ok, detail = self.register(t.astimezone())
        if not ok:
            self.p.set_state("wake_at", iso(t))          # one attempt per target, no retry storm
            self.p.health.write("warn", "wake", f"could not set the wake task: {detail}", now)
            return "wake task not set"
        self.p.set_state("wake_at", iso(t))
        return f"PC will be woken at {t.astimezone().strftime('%a %H:%M')} local for a closing price"
