"""
KAIROS core — de-vig. Sport-agnostic.

Turn bookmaker decimal odds into the *honest* implied probabilities I must beat.
Pure stdlib. No API keys, no network.

Glossary:
  decimal odds d  -> raw implied prob = 1/d
  overround       -> sum of raw implied probs minus 1 (the bookmaker margin / vig)
  de-vig          -> remove the margin so probs sum to 1.0
"""

from __future__ import annotations

import math


def implied_prob(decimal_odds: float) -> float:
    """Raw implied probability from a single decimal price (includes vig)."""
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1.0, got {decimal_odds}")
    return 1.0 / decimal_odds


def overround(odds: list[float]) -> float:
    """Bookmaker margin across a market: Σ(1/odds) − 1. ~0.05–0.08 on football 1X2."""
    return sum(1.0 / o for o in odds) - 1.0


def _check_odds(odds: list[float]) -> None:
    """A market needs at least two prices, every one above 1.0."""
    if len(odds) < 2:
        raise ValueError(f"a market needs at least two prices, got {len(odds)}")
    for o in odds:
        if not o > 1.0:
            raise ValueError(f"decimal odds must be > 1.0, got {o}")


def devig_proportional(odds: list[float]) -> list[float]:
    """
    De-vig by proportional normalization (the simple, robust default).
    Slightly over-shrinks longshots (favorite-longshot bias) — treat longshot
    fair probs as a touch high. Returns probabilities summing to 1.0.
    """
    _check_odds(odds)
    raw = [1.0 / o for o in odds]
    total = sum(raw)
    return [r / total for r in raw]


def devig_multiplicative(odds: list[float]) -> list[float]:
    """Alias kept explicit: multiplicative == proportional for this normalization."""
    return devig_proportional(odds)


def devig_power(odds: list[float], tol: float = 1e-9, max_iter: int = 100) -> list[float]:
    """
    De-vig by the power method: find k so that Σ (1/odds_i)^k = 1.
    Handles favorite-longshot bias better than proportional. Bisection on k.
    """
    _check_odds(odds)
    raw = [1.0 / o for o in odds]

    def s(k: float) -> float:
        return sum(r ** k for r in raw) - 1.0

    lo, hi = 0.5, 2.0
    # ensure the root is bracketed on both sides (s falls as k rises)
    while s(hi) > 0 and hi < 50:
        hi *= 1.5
    while s(lo) < 0 and lo > 1e-3:
        lo /= 2
    if s(hi) > 0 or s(lo) < 0:
        raise ValueError(f"power de-vig could not bracket a solution for odds {odds}")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        val = s(mid)
        if abs(val) < tol:
            break
        if val > 0:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    out = [r ** k for r in raw]
    tot = sum(out)
    return [o / tot for o in out]


def devig_shin(odds: list[float], tol: float = 1e-12, max_iter: int = 200) -> list[float]:
    """
    De-vig by Shin's method. The margin is modelled as the bookmaker's protection
    against a share z of bettors who know the result, which puts more of the
    margin on longshots. Solves for z by bisection so the probabilities sum to 1:

        p_i = ( sqrt(z^2 + 4 (1 - z) q_i^2 / B) - z ) / ( 2 (1 - z) )

    with q_i = 1/odds_i and B = sum of q_i. A market with no margin is returned
    as its implied probabilities.
    """
    _check_odds(odds)
    q = [1.0 / o for o in odds]
    b = sum(q)
    if b <= 1.0 + 1e-12:
        return [x / b for x in q]

    def probs(z: float) -> list[float]:
        return [(math.sqrt(z * z + 4.0 * (1.0 - z) * x * x / b) - z) / (2.0 * (1.0 - z))
                for x in q]

    lo, hi = 0.0, 1.0 - 1e-9               # sum(probs) falls as z rises
    if sum(probs(hi)) > 1.0:
        raise ValueError(f"Shin de-vig could not bracket a solution for odds {odds}")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if sum(probs(mid)) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    out = probs((lo + hi) / 2)
    tot = sum(out)
    return [o / tot for o in out]


DEVIG = {"proportional": devig_proportional, "power": devig_power, "shin": devig_shin}


def market_view(odds_map: dict[str, float], method: str = "proportional") -> dict:
    """
    Full market read for one labelled market.

    Args:
        odds_map: e.g. {"home": 2.10, "draw": 3.40, "away": 3.60}
        method:   "proportional" (default) | "power" | "shin"

    Returns:
        {
          "labels": [...],
          "odds": [...],
          "implied_raw": {...},          # with vig
          "fair_prob": {...},            # de-vigged, sums to 1
          "overround": 0.0xx,
        }
    """
    labels = list(odds_map.keys())
    odds = [odds_map[k] for k in labels]
    if method not in DEVIG:
        raise ValueError(f"unknown de-vig method {method!r}; use one of {sorted(DEVIG)}")
    fair = DEVIG[method](odds)
    return {
        "labels": labels,
        "odds": odds,
        "implied_raw": {k: round(implied_prob(o), 6) for k, o in zip(labels, odds)},
        "fair_prob": {k: round(p, 6) for k, p in zip(labels, fair)},
        "overround": round(overround(odds), 6),
    }


if __name__ == "__main__":
    demo = {"home": 2.10, "draw": 3.40, "away": 3.60}
    v = market_view(demo)
    print("Market:", demo)
    print("Overround:", f"{v['overround']:.2%}")
    print("Fair (de-vigged):", {k: f"{p:.1%}" for k, p in v["fair_prob"].items()})
