"""
KAIROS engine — Poisson + Dixon-Coles (L12/L13).

Builds the full scoreline distribution from expected goals (lambdas), applies the
Dixon-Coles low-score correction, and derives every market: 1X2, Over/Under (any
line), BTTS, correct score. Pure stdlib (math only). No API keys.

The score matrix is the heart of the engine — every probability is read off it,
so it is guaranteed to be internally consistent (all markets sum correctly).
"""

from __future__ import annotations

import math

MAX_GOALS = 10  # truncation; P(>10 goals for one side) is negligible


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lam)."""
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _dc_tau(i: int, j: int, lam_h: float, lam_a: float, rho: float) -> float:
    """
    Dixon-Coles dependence factor for low scores (corrects the independence
    assumption — independent Poisson under-counts 0-0/1-1 draws).
    rho < 0 boosts 0-0 and 1-1, dampens 1-0 and 0-1.
    """
    if i == 0 and j == 0:
        return 1.0 - lam_h * lam_a * rho
    if i == 0 and j == 1:
        return 1.0 + lam_h * rho
    if i == 1 and j == 0:
        return 1.0 + lam_a * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lam_h: float, lam_a: float, rho: float = -0.10,
                 max_goals: int = MAX_GOALS) -> list[list[float]]:
    """
    Full P(home=i, away=j) matrix with Dixon-Coles correction, renormalized to 1.0.
    rho default -0.10 is a typical fitted value for top-league football.
    """
    if lam_h <= 0 or lam_a <= 0:
        raise ValueError(f"lambdas must be > 0, got {lam_h}, {lam_a}")
    m = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    for i in range(max_goals + 1):
        pi = poisson_pmf(i, lam_h)
        for j in range(max_goals + 1):
            pj = poisson_pmf(j, lam_a)
            m[i][j] = pi * pj * _dc_tau(i, j, lam_h, lam_a, rho)
    total = sum(sum(row) for row in m)
    return [[v / total for v in row] for row in m]


def outcome_1x2(m: list[list[float]]) -> dict[str, float]:
    """Home win / draw / away win from the score matrix."""
    home = draw = away = 0.0
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
    return {"home": round(home, 6), "draw": round(draw, 6), "away": round(away, 6)}


def over_under(m: list[list[float]], line: float = 2.5) -> dict[str, float]:
    """Over/Under total goals for a given line (e.g. 2.5)."""
    over = 0.0
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            if i + j > line:
                over += p
    return {f"over_{line}": round(over, 6), f"under_{line}": round(1.0 - over, 6)}


def btts(m: list[list[float]]) -> dict[str, float]:
    """Both teams to score yes/no."""
    yes = 0.0
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            if i >= 1 and j >= 1:
                yes += p
    return {"btts_yes": round(yes, 6), "btts_no": round(1.0 - yes, 6)}


def top_scorelines(m: list[list[float]], n: int = 5) -> list[tuple[str, float]]:
    """Most likely correct scores."""
    flat = [(f"{i}-{j}", p) for i, row in enumerate(m) for j, p in enumerate(row)]
    flat.sort(key=lambda x: x[1], reverse=True)
    return [(s, round(p, 6)) for s, p in flat[:n]]


def expected_goals(m: list[list[float]]) -> tuple[float, float]:
    """Expected goals each side, read back off the matrix (sanity check vs lambdas)."""
    eh = sum(i * sum(row) for i, row in enumerate(m))
    ea = sum(j * sum(m[i][j] for i in range(len(m))) for j in range(len(m[0])))
    return round(eh, 4), round(ea, 4)


def full_markets(lam_h: float, lam_a: float, rho: float = -0.10,
                 ou_lines: tuple[float, ...] = (1.5, 2.5, 3.5)) -> dict:
    """Compute all standard markets from a pair of lambdas in one call."""
    m = score_matrix(lam_h, lam_a, rho)
    markets = {"1x2": outcome_1x2(m), "btts": btts(m)}
    for line in ou_lines:
        markets[f"ou_{line}"] = over_under(m, line)
    markets["top_scores"] = top_scorelines(m)
    markets["expected_goals"] = expected_goals(m)
    return markets


if __name__ == "__main__":
    res = full_markets(1.6, 1.1)
    print("1X2:", {k: f"{v:.1%}" for k, v in res["1x2"].items()})
    print("O/U 2.5:", {k: f"{v:.1%}" for k, v in res["ou_2.5"].items()})
    print("BTTS:", {k: f"{v:.1%}" for k, v in res["btts"].items()})
    print("Top scores:", res["top_scores"])
    print("Expected goals (matrix):", res["expected_goals"])
