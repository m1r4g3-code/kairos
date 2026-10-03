"""
KAIROS core — ask Claude (through the Claude Code CLI on the owner's
subscription, not the paid API) for a judgment, and fail safe.

    out = ask(prompt, model="sonnet", timeout_s=600)
    # -> dict parsed from the first JSON object in Claude's answer, or None

None is returned for every kind of failure: CLI missing, not logged in, usage
limit reached, timeout, non-zero exit, no JSON in the answer. The caller must
treat None as "no judgment" and carry on with the maths result unchanged.

Pure stdlib. Nothing here knows about football.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def find_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    home = os.path.expanduser("~")
    for p in (os.path.join(home, ".local", "bin", "claude.exe"),
              os.path.join(home, ".local", "bin", "claude")):
        if os.path.exists(p):
            return p
    return None


def first_json_object(text: str) -> dict | None:
    """The first balanced {...} in text that parses as a JSON object."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
        start = text.find("{", start + 1)
    return None


def ask(prompt: str, model: str = "sonnet", timeout_s: int = 600,
        allowed_tools: str = "WebSearch", runner=subprocess.run,
        cli: str | None = None) -> tuple[dict | None, str]:
    """
    Returns (parsed JSON or None, a short status for the health log).
    `runner` is injectable so tests never call the real CLI.
    """
    cli = cli or find_cli()
    if not cli:
        return None, "claude CLI not found"
    cmd = [cli, "-p", prompt, "--model", model, "--output-format", "json",
           "--no-session-persistence"]
    if allowed_tools:
        cmd += ["--allowedTools", allowed_tools]
    try:
        proc = runner(cmd, capture_output=True, text=True, timeout=timeout_s,
                      encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout_s}s"
    except OSError as e:
        return None, f"could not start the CLI: {e}"
    if proc.returncode != 0:
        return None, f"exit {proc.returncode}: {(proc.stderr or proc.stdout or '')[:300]}"
    try:
        envelope = json.loads(proc.stdout)
        text = envelope.get("result", "") if isinstance(envelope, dict) else ""
        if isinstance(envelope, dict) and envelope.get("is_error"):
            return None, f"CLI reported an error: {text[:300]}"
    except json.JSONDecodeError:
        text = proc.stdout
    obj = first_json_object(text or "")
    if obj is None:
        return None, "no JSON object in the answer"
    return obj, "ok"
