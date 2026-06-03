"""
KAIROS engine — central constants.

All previously-inline "magic numbers" live here with their rationale, so they are
documented, auditable, and tunable in one place rather than scattered across modules.
Pure stdlib. No API keys.
"""

from __future__ import annotations

# ── Poisson / Dixon-Coles ────────────────────────────────────────────────────
DEFAULT_RHO = -0.10          # typical fitted low-score dependence for top-league football
RHO_MIN, RHO_MAX = -0.20, 0.20  # safe band: keeps the DC tau factors non-negative
MAX_GOALS = 10               # score-matrix truncation; P(>10 goals one side) ~ 0

# ── Elo / strength → expected goals ──────────────────────────────────────────
HOME_ADVANTAGE_ELO = 65.0    # ~65 Elo points is a typical football home edge
ELO_GOALS_DIVISOR = 200.0    # ~100 Elo points ≈ 0.5 goals of supremacy
DEFAULT_TOTAL_GOALS = 2.7    # league/matchup goal expectation when only Elo is known

# ── Monte Carlo ──────────────────────────────────────────────────────────────
SIGMA_SCALER = 0.35          # maps (100-confidence) → lambda uncertainty sigma
MC_DEFAULT_N = 30_000        # simulation count used by the orchestrator
MC_SEED = 7                  # fixed seed: reproducible cross-check of the analytic engine

# ── Value (L15) + Staking (L16) ──────────────────────────────────────────────
DEFAULT_FRACTION = 0.25      # ¼ Kelly
DEFAULT_CAP = 0.05           # max 5% of bankroll on a single bet
CONFIDENCE_FLOOR = 45.0      # below this → stake 0 (pass)
MIN_EDGE = 0.03              # require +3% EV to bet
MAX_EXPOSURE = 0.15          # max combined live exposure across all active bets

# ── Sensitivity / fragility (L14) ────────────────────────────────────────────
SENSITIVITY_PERTURB = 0.15   # ±15% lambda perturbation used to fragility-test a bet
