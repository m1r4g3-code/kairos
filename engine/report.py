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
import sys

from run import build_prediction

# A short favourite this much over my number = an overpriced "banker" trap.
TRAP_MIN_IMPLIED = 0.65      # only short favourites can be "bankers"
TRAP_MIN_GAP = 0.08          # bookie % at least 8 pts above my %


def _implied(odds: float) -> float:
    return 1.0 / odds


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
        return "NO (TRAP)"
    if s["robust"] and s["fav"] in s["value_bets"]:
        return "BET"
    return "NO"


def render_card(preds: list[dict]) -> str:
    """Render the full slip as one plain-text chart."""
    rows = [summarize(p) for p in preds]
    out: list[str] = []
    bar = "=" * 78
    out.append(bar)
    out.append("  KAIROS CARD READER   (rule: my % HIGHER than bookie = bet; LOWER = skip)")
    out.append(bar)
    out.append(f"  {'MATCH':<34}{'FAV PICK':<14}{'BOOKIE':>7}{'ME':>6}  DECISION")
    out.append("  " + "-" * 74)
    for s in rows:
        fav = s["fav"]
        if not fav:
            out.append(f"  {s['match'][:33]:<34}{'(no odds)':<14}{'':>7}{'':>6}  SKIP")
            continue
        pick = f"{fav['selection']}@{fav['odds']:.2f}"
        out.append(
            f"  {s['match'][:33]:<34}{pick:<14}"
            f"{s['fav_implied']*100:>6.0f}%{fav['my_prob']*100:>5.0f}%"
            f"  {_decision(s)}"
        )
    out.append("  " + "-" * 74)

    # Robust value bets (the only real YES) vs fragile darts.
    robust_bets = [(s, b) for s in rows for b in s["value_bets"] if s["robust"]]
    fragile_bets = [(s, b) for s in rows for b in s["value_bets"] if not s["robust"]]

    if robust_bets:
        out.append("  VALUE BETS TO PLACE:")
        for s, b in robust_bets:
            out.append(f"     {s['match'][:40]} -> {b['selection']} @{b['odds']:.2f} "
                       f"(me {b['my_prob']*100:.0f}% vs bookie {_implied(b['odds'])*100:.0f}%)")
    else:
        out.append("  VALUE BETS TO PLACE: none  ->  best move is bet nothing.")

    if fragile_bets:
        out.append("  SPECULATIVE DARTS ONLY (fragile / thin data - small stake at most):")
        for s, b in fragile_bets:
            out.append(f"     {s['match'][:40]} -> {b['selection']} @{b['odds']:.2f}")

    # Reddest trap = biggest overpriced short favourite.
    traps = [s for s in rows if s["trap"]]
    if traps:
        worst = max(traps, key=lambda s: s["gap"])
        f = worst["fav"]
        out.append("  REDDEST TRAP (avoid most): "
                   f"{worst['match'][:40]} {f['selection']}@{f['odds']:.2f} "
                   f"-> bookie {worst['fav_implied']*100:.0f}% but me only {f['my_prob']*100:.0f}%")
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
