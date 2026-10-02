"""
KAIROS engine — football settlement rules for the ledger.

Decides whether a logged pick won, from the final score when there is one:
1X2, over/under on any half or whole line (a whole-line exact total is a push),
and both-teams-to-score. Installed into core.ledger by the engine/ledger.py shim.

Pure stdlib.
"""

from __future__ import annotations


def parse_score(result: dict) -> tuple[int, int] | None:
    s = result.get("score")
    if isinstance(s, str) and "-" in s:
        try:
            h, a = s.split("-")
            return int(h.strip()), int(a.strip())
        except ValueError:
            return None
    return None


def settle_football(pick: dict, result: dict) -> bool | None:
    """
    Did this pick win? Returns True/False, or None when the result is a PUSH/void
    or cannot be determined (so it is excluded from scoring rather than guessed).
    """
    market = pick.get("market", "")
    sel = pick.get("selection", "")
    goals = parse_score(result)
    outcome = result.get("outcome")

    if market == "1x2":
        if goals is not None:
            h, a = goals
            res = "home" if h > a else "draw" if h == a else "away"
            return res == sel
        if outcome in ("home", "draw", "away"):
            return outcome == sel
        if outcome in ("win", "lose"):
            return outcome == "win"
        return None

    if market.startswith("ou_"):
        if goals is None:
            return outcome == "win" if outcome in ("win", "lose") else None
        total = goals[0] + goals[1]
        try:
            line = float(market.split("_", 1)[1])
        except (IndexError, ValueError):
            return None
        if total == line:          # whole-number line landed exactly → push/void
            return None
        over = total > line
        return over if sel.startswith("over") else (not over)

    if market == "btts":
        if goals is None:
            return outcome == "win" if outcome in ("win", "lose") else None
        yes = goals[0] >= 1 and goals[1] >= 1
        return yes if sel == "btts_yes" else (not yes)

    # Unknown market: fall back to explicit win/lose, else selection match.
    if outcome in ("win", "lose"):
        return outcome == "win"
    return outcome == sel if outcome is not None else None
