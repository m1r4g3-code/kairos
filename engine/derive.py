"""
KAIROS engine — price cousin markets from the sharp line.

The sharp book prices 1X2 and one goal line well. Many markets the user is
offered (other goal lines, Asian handicaps, double chance, draw no bet) have no
sharp price in the feed. This module fits a Dixon-Coles score matrix to the
sharp prices that do exist and reads the other markets off it.

  fit_from_1x2(fair)                      expected goals that reproduce a fair 1X2
  fit_from_1x2_and_total(fair, p_over)    ... and a fair over/under as well
  fit_from_1x2_and_total_prices(...)      same, from the quoted over/under prices
                                          at any line, quarter lines included
  total_settlement(m, line, side)         how an over/under bet settles, any line
  handicap_settlement(m, line, side)      how an Asian handicap bet settles
  settlement_ev(s, price) / fair_price(s) value of a bet with that settlement
  double_chance(fair) / draw_no_bet(fair) straight from the fair 1X2, no model

Quarter lines (2.25, 2.75, -0.25, ...) are two half-stake bets on the lines
either side. A settlement is therefore five probabilities: win, half_win, push,
half_loss, loss.

Pure stdlib.
"""

from __future__ import annotations

import math

import constants
import poisson

LAM_MIN, LAM_MAX = 0.05, 8.0
OUTCOMES = ("win", "half_win", "push", "half_loss", "loss")


# ── fitting ──────────────────────────────────────────────────────────────────

def _clamp(x: float) -> float:
    return min(LAM_MAX, max(LAM_MIN, x))


def _solve(residual, lam_h: float, lam_a: float, tol: float = 1e-10,
           max_iter: int = 60) -> tuple[float, float]:
    """Damped Newton on two unknowns with a numeric Jacobian."""
    for _ in range(max_iter):
        r1, r2 = residual(lam_h, lam_a)
        if abs(r1) < tol and abs(r2) < tol:
            break
        eh, ea = 1e-5 * lam_h, 1e-5 * lam_a
        a1, a2 = residual(lam_h + eh, lam_a)
        b1, b2 = residual(lam_h, lam_a + ea)
        j11, j21 = (a1 - r1) / eh, (a2 - r2) / eh
        j12, j22 = (b1 - r1) / ea, (b2 - r2) / ea
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-14:
            break
        dh = (-r1 * j22 + r2 * j12) / det
        da = (-r2 * j11 + r1 * j21) / det
        # never move a lambda by more than half its size in one step
        scale = min(1.0, 0.5 * lam_h / abs(dh) if dh else 1.0, 0.5 * lam_a / abs(da) if da else 1.0)
        lam_h, lam_a = _clamp(lam_h + scale * dh), _clamp(lam_a + scale * da)
    return lam_h, lam_a


def _start(fair: dict) -> tuple[float, float]:
    d = fair["home"] - fair["away"]
    return _clamp(1.35 + 0.9 * d), _clamp(1.35 - 0.9 * d)


def fit_from_1x2(fair: dict, rho: float = constants.DEFAULT_RHO) -> tuple[float, float]:
    """Expected goals (home, away) whose score matrix reproduces the fair 1X2."""
    def residual(lh, la):
        x = poisson.outcome_1x2(poisson.score_matrix(lh, la, rho), ndigits=None)
        return x["home"] - fair["home"], x["away"] - fair["away"]
    return _solve(residual, *_start(fair))


def fit_from_1x2_and_total(fair: dict, p_over: float, line: float = 2.5,
                           rho: float = constants.DEFAULT_RHO) -> tuple[float, float]:
    """
    Expected goals whose score matrix reproduces the fair home-minus-away margin
    and the fair probability of going over `line` (a half line).
    """
    target = fair["home"] - fair["away"]

    def residual(lh, la):
        m = poisson.score_matrix(lh, la, rho)
        x = poisson.outcome_1x2(m, ndigits=None)
        over = sum(p for i, row in enumerate(m) for j, p in enumerate(row) if i + j > line)
        return x["home"] - x["away"] - target, over - p_over
    return _solve(residual, *_start(fair))


def fit_from_1x2_and_total_prices(fair: dict, line: float, over_price: float,
                                  under_price: float,
                                  rho: float = constants.DEFAULT_RHO) -> tuple[float, float]:
    """
    Expected goals from the fair 1X2 margin and the sharp book's quoted over and
    under prices at `line`, which may be a whole, half or quarter line.

    The margin is assumed to sit equally on both prices, so the matrix is fitted
    to make its own fair prices stand in the same ratio as the quoted ones:
        fair_price(over) / fair_price(under) = over_price / under_price
    On a half line this is the proportional de-vig. On whole and quarter lines
    it accounts for pushes and half results, which a plain de-vig cannot.
    """
    if over_price <= 1.0 or under_price <= 1.0:
        raise ValueError("prices must be > 1.0")
    target = fair["home"] - fair["away"]
    want = math.log(over_price / under_price)

    def residual(lh, la):
        m = poisson.score_matrix(lh, la, rho)
        x = poisson.outcome_1x2(m, ndigits=None)
        fo = fair_price(total_settlement(m, line, "over"))
        fu = fair_price(total_settlement(m, line, "under"))
        return x["home"] - x["away"] - target, math.log(fo / fu) - want
    return _solve(residual, *_start(fair))


# ── settlement ───────────────────────────────────────────────────────────────

def _split(line: float) -> list[float]:
    """A quarter line is two half-stake bets on the neighbouring lines."""
    doubled = line * 2
    if doubled == int(doubled):
        return [line]
    if (line * 4) != int(line * 4):
        raise ValueError(f"{line} is not a whole, half or quarter line")
    return [line - 0.25, line + 0.25]


def _settle(dist: dict[float, float], line: float) -> dict[str, float]:
    """
    dist maps a margin (already signed so that positive is good for the bettor
    before the line is applied) to its probability. The bet wins when
    margin + line > 0.
    """
    parts = _split(line)
    out = dict.fromkeys(OUTCOMES, 0.0)
    for margin, p in dist.items():
        score = 0.0                          # +1 win, 0 push, -1 loss, averaged over parts
        for part in parts:
            v = margin + part
            score += (1.0 if v > 1e-9 else -1.0 if v < -1e-9 else 0.0) / len(parts)
        key = {1.0: "win", 0.5: "half_win", 0.0: "push", -0.5: "half_loss", -1.0: "loss"}[score]
        out[key] += p
    return out


def total_settlement(m: list[list[float]], line: float, side: str = "over") -> dict[str, float]:
    """How an over or under bet on total goals at `line` settles."""
    if side not in ("over", "under"):
        raise ValueError("side must be 'over' or 'under'")
    dist: dict[float, float] = {}
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            t = float(i + j)
            dist[t] = dist.get(t, 0.0) + p
    if side == "over":
        return _settle(dist, -line)                       # wins when total - line > 0
    return _settle({-t: p for t, p in dist.items()}, line)   # wins when line - total > 0


def handicap_settlement(m: list[list[float]], line: float, side: str = "home") -> dict[str, float]:
    """
    How an Asian handicap bet settles. `line` is the handicap given to the side
    being backed: home -0.5 wins when home wins; away +0.5 wins unless home wins.
    """
    if side not in ("home", "away"):
        raise ValueError("side must be 'home' or 'away'")
    dist: dict[float, float] = {}
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            d = float(i - j) if side == "home" else float(j - i)
            dist[d] = dist.get(d, 0.0) + p
    return _settle(dist, line)


def settlement_ev(s: dict[str, float], price: float) -> float:
    """Expected profit per unit staked at decimal `price`."""
    win = price - 1.0
    return (s["win"] * win + s["half_win"] * win / 2.0
            - s["half_loss"] / 2.0 - s["loss"])


def fair_price(s: dict[str, float]) -> float | None:
    """The decimal price at which the bet has zero expected profit."""
    gain = s["win"] + s["half_win"] / 2.0
    lose = s["loss"] + s["half_loss"] / 2.0
    return None if gain <= 0 else 1.0 + lose / gain


# ── straight from the fair 1X2 ───────────────────────────────────────────────

def double_chance(fair: dict) -> dict[str, float]:
    """Fair probabilities for 1X, 12 and X2."""
    return {"1X": fair["home"] + fair["draw"], "12": fair["home"] + fair["away"],
            "X2": fair["draw"] + fair["away"]}


def draw_no_bet(fair: dict) -> dict[str, float]:
    """Fair win probabilities with the draw refunded (they sum to 1)."""
    t = fair["home"] + fair["away"]
    return {"home": fair["home"] / t, "away": fair["away"] / t}


if __name__ == "__main__":
    fair = {"home": 0.52, "draw": 0.26, "away": 0.22}
    lh, la = fit_from_1x2_and_total(fair, p_over=0.55)
    m = poisson.score_matrix(lh, la)
    print(f"expected goals {lh:.3f} - {la:.3f}")
    for ln in (2.25, 2.5, 2.75, 3.0):
        print(f"  over {ln}: fair price {fair_price(total_settlement(m, ln)):.3f}")
    for ln in (-0.25, -0.5, -0.75, -1.0):
        print(f"  home {ln:+}: fair price {fair_price(handicap_settlement(m, ln)):.3f}")
    print("  double chance:", {k: round(1 / v, 3) for k, v in double_chance(fair).items()})
