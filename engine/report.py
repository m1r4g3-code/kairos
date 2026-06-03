"""
KAIROS engine — report renderer (the output layer).

Turns one or more engine predictions into ONE consistent, plain-English card:
for each match it shows the favourite people want to bet, the BOOKIE's % vs MY %,
a clear YES/NO, and flags the single reddest "trap" (an overpriced short favourite).

This exists so the chart looks the same every time instead of being hand-drawn.
Console-safe ASCII only (renders cleanly on Windows). Pure stdlib.

CLI:
    python report.py spec1.json spec2.json ...   # render a whole slip
"""

from __future__ import annotations

import json
import re
import sys

from run import build_prediction

# A short favourite this much over my number = an overpriced "banker" trap.
TRAP_MIN_IMPLIED = 0.65      # only short favourites can be "bankers"
TRAP_MIN_GAP = 0.08          # odds' % at least 8 pts above my %


def _implied(odds: float) -> float:
    return 1.0 / odds


def _teams(match: str) -> tuple[str | None, str | None]:
    """Split a 'Home v Away' (or 'Home vs Away') match string into team names."""
    parts = re.split(r"\s+vs?\s+", match, maxsplit=1)
    if len(parts) != 2:
        return None, None
    clean = lambda s: re.sub(r"\s*\(.*?\)", "", s).strip()   # drop parenthetical notes
    return clean(parts[0]), clean(parts[1])


def _side_name(selection: str, home: str | None, away: str | None) -> str:
    """Turn home/draw/away into a human label with the team name + venue."""
    if selection == "home" and home:
        return f"{home} (HOME)"
    if selection == "away" and away:
        return f"{away} (AWAY)"
    if selection == "draw":
        return "Draw"
    return selection


def summarize(pred: dict) -> dict:
    """Condense one engine prediction into the few facts the chart needs."""
    vt = pred.get("value_table", [])
    fav = min(vt, key=lambda r: r["odds"]) if vt else None
    value_bets = [r for r in vt if r["bet"]]
    robust = pred["verdict"].startswith("BET")     # BET = robust; SPECULATIVE = fragile
    fav_implied = _implied(fav["odds"]) if fav else 0.0
    gap = fav_implied - fav["my_prob"] if fav else 0.0
    trap = bool(fav) and fav_implied >= TRAP_MIN_IMPLIED and gap >= TRAP_MIN_GAP
    return {
        "match": pred.get("match", "?"),
        "fav": fav, "fav_implied": fav_implied, "gap": gap,
        "value_bets": value_bets, "robust": robust, "trap": trap,
        "verdict": pred["verdict"],
    }


def _decision(s: dict) -> str:
    """One clear token for the favourite line."""
    if s["trap"]:
        return "SKIP (TRAP)"
    if s["robust"] and s["fav"] in s["value_bets"]:
        return "BET"
    return "SKIP"


def render_card(preds: list[dict]) -> str:
    """Render the full slip as one plain-text chart (team names + home/away)."""
    rows = [summarize(p) for p in preds]
    out: list[str] = []
    bar = "=" * 80
    out.append(bar)
    out.append("  KAIROS CARD READER")
    out.append("  I bet ONLY when my % is higher than the odds' % (that means good value).")
    out.append("  ODDS% = chance the SportyBet price implies.   MY% = chance I think is real.")
    out.append(bar)
    out.append(f"  {'WHO TO BACK (the favourite)':<34}{'ODDS':>6}{'ODDS%':>7}{'MY%':>6}  WHAT TO DO")
    out.append("  " + "-" * 76)
    for s in rows:
        fav = s["fav"]
        home, away = _teams(s["match"])
        if not fav:
            out.append(f"  {s['match'][:33]:<34}{'':>6}{'':>7}{'':>6}  SKIP (no odds)")
            continue
        who = _side_name(fav["selection"], home, away)
        out.append(
            f"  {who[:33]:<34}{fav['odds']:>6.2f}"
            f"{s['fav_implied']*100:>6.0f}%{fav['my_prob']*100:>5.0f}%"
            f"  {_decision(s)}"
        )
    out.append("  " + "-" * 76)

    # Robust value bets (the only real BET) vs fragile darts.
    robust_bets = [(s, b) for s in rows for b in s["value_bets"] if s["robust"]]
    fragile_bets = [(s, b) for s in rows for b in s["value_bets"] if not s["robust"]]

    def _line(s, b):
        home, away = _teams(s["match"])
        who = _side_name(b["selection"], home, away)
        return (f"     {who} @{b['odds']:.2f}  "
                f"(my {b['my_prob']*100:.0f}% beats the odds' {_implied(b['odds'])*100:.0f}%)")

    if robust_bets:
        out.append("  >>> BET THESE (good value):")
        for s, b in robust_bets:
            out.append(_line(s, b))
    else:
        out.append("  >>> BET THESE: none today -> the smart move is bet nothing.")

    if fragile_bets:
        out.append("  >>> TINY PUNT ONLY (shaky / not enough data - small money at most):")
        for s, b in fragile_bets:
            out.append(_line(s, b))

    # Reddest trap = biggest overpriced short favourite.
    traps = [s for s in rows if s["trap"]]
    if traps:
        worst = max(traps, key=lambda s: s["gap"])
        f = worst["fav"]
        home, away = _teams(worst["match"])
        who = _side_name(f["selection"], home, away)
        out.append(f"  >>> AVOID MOST (fake 'banker'): {who} @{f['odds']:.2f}  "
                   f"-> odds say {worst['fav_implied']*100:.0f}% but I say only {f['my_prob']*100:.0f}%")
    out.append(bar)
    return "\n".join(out)


def main() -> None:
    specs = []
    for path in sys.argv[1:]:
        with open(path, "r", encoding="utf-8") as fh:
            specs.append(build_prediction(json.load(fh)))
    if not specs:
        print("usage: python report.py spec1.json [spec2.json ...]")
        return
    print(render_card(specs))


if __name__ == "__main__":
    main()
