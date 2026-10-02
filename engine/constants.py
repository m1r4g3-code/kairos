"""
KAIROS engine — central constants.

All previously-inline "magic numbers" live here with their rationale, so they are
documented, auditable, and tunable in one place rather than scattered across modules.
Pure stdlib. No API keys.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import staking as _staking  # noqa: E402

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
# Defined once, in core/staking.py; re-exported here for the football engine.
DEFAULT_FRACTION = _staking.DEFAULT_FRACTION
DEFAULT_CAP = _staking.DEFAULT_CAP
CONFIDENCE_FLOOR = _staking.CONFIDENCE_FLOOR
MIN_EDGE = _staking.MIN_EDGE
MAX_EXPOSURE = _staking.MAX_EXPOSURE

# ── Judgment modifiers ───────────────────────────────────────────────────────
# A qualitative nudge may move expected goals by at most 20% either way
# (about 0.3 goals at a typical 1.5). Outside this the spec is rejected.
MODIFIER_MIN, MODIFIER_MAX = 0.80, 1.20

# ── Sharp reference (edge.py) ────────────────────────────────────────────────
MIN_CONSENSUS_BOOKS = 3      # without a sharp book, fewer books than this is no reference

# ── Sensitivity / fragility (L14) ────────────────────────────────────────────
SENSITIVITY_PERTURB = 0.15   # ±15% lambda perturbation used to fragility-test a bet
