"""
KAIROS engine — Sharp-line edge (the v2.0 core).

The proven retail edge against a soft bookmaker is NOT out-predicting the market
from scratch — it is comparing the soft book (SportyBet) to the SHARPEST market
(Pinnacle / sharp consensus), whose de-vigged price is the closest thing to the
"true" probability. Where SportyBet pays more than the sharp fair price, that gap
is real, measurable value.

This module:
  - sharp_fair(book_odds)      pick the sharp reference, de-vig -> true probs
  - value_vs_sharp(sb, fair)   EV of each SportyBet selection vs the sharp truth
  - agree(engine_dist, fair)   cross-check: does the data-fed engine agree?

Pure stdlib. De-vig is reused from market.py (no new probability code).
"""

from __future__ import annotations

import config
import market


def sharp_fair(book_odds: dict[str, dict[str, float]],
               sharp_priority: tuple[str, ...] = config.SHARP_PRIORITY,
               method: str = "power") -> dict | None:
    """
    Turn many bookmakers' odds into the sharp "true" probabilities.

    Args:
        book_odds: {bookmaker_key: {selection: decimal_odds}} for ONE market.
        sharp_priority: which book to trust first; falls back to a de-vigged
            consensus (average) across all books if no priority book is present.

    Returns:
        {"source": <book or "consensus">, "fair_prob": {sel: p}, "n_books": k}
        or None if there's nothing usable.
    """
    books = {b: o for b, o in book_odds.items() if o and len(o) >= 2}
    if not books:
        return None

    # 1) Prefer a named sharp book.
    for b in sharp_priority:
        if b in books:
            fair = market.market_view(books[b], method=method)["fair_prob"]
            return {"source": b, "fair_prob": fair, "n_books": 1}

    # 2) Otherwise, de-vig every book and average per selection (consensus).
    sels = set().union(*(o.keys() for o in books.values()))
    acc: dict[str, list[float]] = {s: [] for s in sels}
    for o in books.values():
        fair = market.market_view(o, method=method)["fair_prob"]
        for s, p in fair.items():
            acc[s].append(p)
    avg = {s: sum(v) / len(v) for s, v in acc.items() if v}
    total = sum(avg.values())
    fair = {s: round(p / total, 6) for s, p in avg.items()}     # renormalize
    return {"source": "consensus", "fair_prob": fair, "n_books": len(books)}


def value_vs_sharp(sb_odds: dict[str, float], fair: dict[str, float],
                   min_edge: float = config.MIN_EDGE) -> list[dict]:
    """
    Compare SportyBet's price for each selection to the sharp true probability.
    EV = sb_odds * sharp_prob - 1. Positive beyond min_edge => genuine value.
    """
    rows = []
    for sel, price in sb_odds.items():
        p = fair.get(sel)
        if p is None:
            continue
        ev = price * p - 1.0
        rows.append({
            "selection": sel,
            "sb_odds": price,
            "sb_implied": round(1.0 / price, 4),
            "sharp_prob": round(p, 4),
            "ev": round(ev, 4),
            "value": ev > min_edge,
        })
    rows.sort(key=lambda r: r["ev"], reverse=True)
    return rows


def agree(engine_1x2: dict[str, float], fair: dict[str, float]) -> dict:
    """
    Cross-check: how closely does the data-fed Poisson engine agree with the
    sharp line on 1X2? Small total deviation => high confidence; large => caution.
    """
    keys = ("home", "draw", "away")
    if not all(k in engine_1x2 and k in fair for k in keys):
        return {"deviation": None, "aligned": None}
    dev = sum(abs(engine_1x2[k] - fair[k]) for k in keys) / 2.0  # total variation
    return {"deviation": round(dev, 4), "aligned": dev < 0.08}


if __name__ == "__main__":
    # Demo: a soft book (sportybet) overpricing the home side vs Pinnacle.
    demo = {
        "pinnacle":  {"home": 1.80, "draw": 3.90, "away": 4.50},
        "sportybet": {"home": 1.95, "draw": 3.80, "away": 4.30},
    }
    sf = sharp_fair(demo)
    print("Sharp source:", sf["source"], "fair:", sf["fair_prob"])
    for r in value_vs_sharp(demo["sportybet"], sf["fair_prob"]):
        tag = "  <-- VALUE" if r["value"] else ""
        print(f"  {r['selection']:5} @{r['sb_odds']}  sharp {r['sharp_prob']*100:.1f}%"
              f"  EV {r['ev']*100:+.1f}%{tag}")
