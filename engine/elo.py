"""
KAIROS engine — Elo & strength → expected goals (L2 → L12 bridge).

Two ways to reach the lambdas the Poisson model needs:
  1. From attack/defense strengths relative to a league baseline (Dixon-Coles style).
  2. From Elo ratings (when that's all that's available) -> supremacy -> lambdas.

Pure stdlib. No API keys.
"""

from __future__ import annotations

import constants

_HFA = constants.HOME_ADVANTAGE_ELO
_GOALS_DIVISOR = constants.ELO_GOALS_DIVISOR


# ── Elo basics ───────────────────────────────────────────────────────────────

def elo_expected_score(rating_home: float, rating_away: float,
                       home_advantage: float = _HFA) -> float:
    """
    Elo expected score for the home side (0..1), home_advantage in Elo points
    (~65 is a typical football value). This is win+½·draw, not pure win prob.
    """
    diff = (rating_home + home_advantage) - rating_away
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def elo_supremacy(rating_home: float, rating_away: float,
                  home_advantage: float = _HFA) -> float:
    """
    Convert an Elo gap into an expected goal *supremacy* (home minus away goals).
    Calibrated so ~100 Elo points ≈ ~0.5 goals of supremacy (typical football).
    """
    diff = (rating_home + home_advantage) - rating_away
    return diff / _GOALS_DIVISOR


def elo_to_lambdas(rating_home: float, rating_away: float,
                   total_goals: float = constants.DEFAULT_TOTAL_GOALS,
                   home_advantage: float = _HFA,
                   ) -> tuple[float, float]:
    """
    Split an expected total-goals environment into home/away lambdas using the
    Elo-implied supremacy. total_goals is the league/matchup goal expectation.
        lam_home - lam_away = supremacy
        lam_home + lam_away = total_goals
    """
    sup = elo_supremacy(rating_home, rating_away, home_advantage)
    lam_h = max(0.15, (total_goals + sup) / 2.0)
    lam_a = max(0.15, (total_goals - sup) / 2.0)
    return round(lam_h, 4), round(lam_a, 4)


# ── Strength → lambdas (preferred when xG / goal data is available) ───────────

def strengths_to_lambdas(
    att_home: float, def_home: float,
    att_away: float, def_away: float,
    league_home_avg: float = 1.50,
    league_away_avg: float = 1.20,
    home_mult: float = 1.0,
) -> tuple[float, float]:
    """
    Dixon-Coles style expected goals from relative strengths (1.0 = league average).

        lam_home = league_home_avg * att_home * def_away * home_mult
        lam_away = league_away_avg * att_away * def_home

    att_x  > 1 means an above-average attack; def_x > 1 means a *leaky* defense
    (higher = concedes more), so multiplying by the opponent's def works directly.
    home_mult applies any extra venue boost on top of the baked-in home/away split.
    """
    lam_h = league_home_avg * att_home * def_away * home_mult
    lam_a = league_away_avg * att_away * def_home
    return round(max(0.15, lam_h), 4), round(max(0.15, lam_a), 4)


def update_elo(rating: float, expected: float, actual: float, k: float = 20.0) -> float:
    """Post-match Elo update (actual: 1 win / 0.5 draw / 0 loss). For the L19 loop."""
    return round(rating + k * (actual - expected), 2)


if __name__ == "__main__":
    print("Elo expected (home):", round(elo_expected_score(1600, 1500), 3))
    print("Elo lambdas:", elo_to_lambdas(1600, 1500, total_goals=2.7))
    print("Strength lambdas:", strengths_to_lambdas(1.2, 0.9, 1.0, 1.1, home_mult=1.15))
