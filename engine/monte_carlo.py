"""
KAIROS engine — Monte Carlo simulation (L12).

The analytic Poisson/Dixon-Coles matrix already gives exact market probabilities.
Monte Carlo earns its keep when we want to:
  - inject *lambda uncertainty* (our expected-goals estimate is itself noisy), which
    fattens the tails and gives more honest probabilities under low confidence;
  - cross-check the analytic engine (the two should agree within sampling error).

Pure stdlib (random + math). No numpy dependency, no API keys.
"""

from __future__ import annotations

import math
import random


def _sample_poisson(lam: float, rng: random.Random) -> int:
    """Knuth's algorithm for sampling a Poisson(lam) variate."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def simulate(lam_h: float, lam_a: float, n: int = 50_000,
             lambda_sigma: float = 0.0, seed: int | None = None) -> dict:
    """
    Simulate the match n times.

    lambda_sigma > 0 draws each game's lambdas from a log-normal around the point
    estimate (multiplicative noise), modelling our uncertainty about expected goals.
    Set it from confidence: low confidence -> larger sigma -> fatter tails.

    Returns 1X2, O/U 2.5, BTTS probabilities plus expected goals — same shape as
    the analytic engine so they can be compared directly.
    """
    rng = random.Random(seed)
    home = draw = away = over25 = btts_yes = 0
    sum_h = sum_a = 0

    for _ in range(n):
        if lambda_sigma > 0:
            lh = lam_h * math.exp(rng.gauss(0, lambda_sigma))
            la = lam_a * math.exp(rng.gauss(0, lambda_sigma))
        else:
            lh, la = lam_h, lam_a
        gh = _sample_poisson(lh, rng)
        ga = _sample_poisson(la, rng)
        sum_h += gh
        sum_a += ga
        if gh > ga:
            home += 1
        elif gh == ga:
            draw += 1
        else:
            away += 1
        if gh + ga > 2.5:
            over25 += 1
        if gh >= 1 and ga >= 1:
            btts_yes += 1

    return {
        "n": n,
        "1x2": {"home": round(home / n, 6), "draw": round(draw / n, 6),
                "away": round(away / n, 6)},
        "ou_2.5": {"over_2.5": round(over25 / n, 6),
                   "under_2.5": round(1 - over25 / n, 6)},
        "btts": {"btts_yes": round(btts_yes / n, 6),
                 "btts_no": round(1 - btts_yes / n, 6)},
        "expected_goals": (round(sum_h / n, 4), round(sum_a / n, 4)),
    }


if __name__ == "__main__":
    res = simulate(1.6, 1.1, n=50_000, seed=42)
    print(f"MC 1X2: {res['1x2']}")
    print(f"MC O/U 2.5: {res['ou_2.5']}")
    print(f"MC BTTS: {res['btts']}")
    res2 = simulate(1.6, 1.1, n=50_000, lambda_sigma=0.25, seed=42)
    print(f"MC 1X2 (with lambda uncertainty): {res2['1x2']}")
