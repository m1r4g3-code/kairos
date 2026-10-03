"""
KAIROS core — file state that survives being killed at any moment.

  save_json / load_json   whole-file state, written to a temp file and renamed,
                          so a crash leaves either the old or the new file
  KeyedLog                append-only JSONL where every record has a key; a key
                          already present is never written twice, so running a
                          job twice cannot double-log
  SingleInstance          a lock file so two copies of a loop cannot run at once;
                          a lock left by a dead process is taken over

Pure stdlib. Nothing here knows about football.
"""

from __future__ import annotations

import json
import os
import sys
import time


def save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


class KeyedLog:
    """Append-only JSONL file of records that each carry a unique `key`."""

    def __init__(self, path: str):
        self.path = path
        self._keys: set | None = None

    def records(self) -> list[dict]:
        out = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue                  # a torn last line is skipped
        except FileNotFoundError:
            pass
        return out

    def keys(self) -> set:
        if self._keys is None:
            self._keys = {r.get("key") for r in self.records()}
        return self._keys

    def has(self, key: str) -> bool:
        return key in self.keys()

    def add(self, rec: dict) -> bool:
        """Append rec unless its key is already present. Returns True if written."""
        if "key" not in rec:
            raise ValueError("record needs a 'key'")
        if self.has(rec["key"]):
            return False
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=True, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.keys().add(rec["key"])
        return True

    def latest(self) -> dict:
        """Records by key (keys are unique, so this is a lookup table)."""
        out: dict = {}
        for r in self.records():
            out[r.get("key")] = r
        return out


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259                                          # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class SingleInstance:
    """
    with SingleInstance(path): ...   raises RuntimeError if another live process
    holds the lock. A lock whose process has died is taken over.
    """

    def __init__(self, path: str):
        self.path = path
        self.held = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{os.getpid()} {time.time():.0f}")
                self.held = True
                return self
            except FileExistsError:
                try:
                    with open(self.path) as f:
                        pid = int(f.read().split()[0])
                except (OSError, ValueError, IndexError):
                    pid = -1
                if _pid_alive(pid):
                    raise RuntimeError(f"another copy is running (pid {pid}, lock {self.path})")
                try:
                    os.remove(self.path)          # stale lock from a dead process
                except FileNotFoundError:
                    pass
        raise RuntimeError(f"could not take the lock {self.path}")

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass
            self.held = False
        return False
