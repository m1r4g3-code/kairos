"""
KAIROS engine — Value (L15) + Staking (L16).

EV detection and fractional-Kelly stake sizing with hard guardrails. This is the
module that protects real money: every safety rail (fraction, cap, confidence
floor, min edge) lives here. Pure stdlib. No API keys, no bet placement — sizing only.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Defaults (see knowledge/staking-kelly.md) ────────────────────────────────
DEFAULT_FRACTION = 0.25        # ¼ Kelly
DEFAULT_CAP = 0.05             # max 5% of bankroll on one bet
CONFIDENCE_FLOOR = 45.0        # below this -> stake 0 (pass)
MIN_EDGE = 0.03                # require +3% EV to bet


def expected_value(prob: float, decimal_odds: float) -> float:
    """EV per unit staked: (prob * odds) - 1. Positive => the bet has value."""
    return prob * decimal_odds - 1.0


def kelly_fraction(prob: float, decimal_odds: float) -> float:
    """
    Full Kelly fraction of bankroll. Negative/zero => no edge => no bet.
        b = odds - 1 ;  f* = (b*p - q) / b
    """
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob
    f = (b * prob - q) / b
    return max(0.0, f)


@dataclass
class Stake:
    market: str
    selection: str
    odds: float
    my_prob: float
    fair_prob: float          # de-vigged market probability
    ev: float
    edge_vs_market: float     # my_prob - fair_prob
    full_kelly: float
    stake_fraction: float     # final fraction of bankroll
    stake_units: float
    bet: bool
    reason: str


def size_bet(
    market: str,
    selection: str,
    my_prob: float,
    decimal_odds: float,
    fair_prob: float,
    confidence: float,
    bankroll: float = 100.0,
    fraction: float = DEFAULT_FRACTION,
    cap: float = DEFAULT_CAP,
    min_edge: float = MIN_EDGE,
    confidence_floor: float = CONFIDENCE_FLOOR,
) -> Stake:
    """
    Decide whether to bet and how much. Applies, in order:
      1. EV gate (must clear min_edge),
      2. confidence floor (below -> pass),
      3. fractional Kelly,
      4. confidence scaling,
      5. hard cap.
    """
    ev = expected_value(my_prob, decimal_odds)
    edge = my_prob - fair_prob
    full = kelly_fraction(my_prob, decimal_odds)

    bet = True
    reason = "value bet"
    if ev < min_edge:
        bet, reason = False, f"EV {ev:+.1%} below min edge {min_edge:.0%}"
    elif confidence < confidence_floor:
        bet, reason = False, f"confidence {confidence:.0f} below floor {confidence_floor:.0f}"
    elif full <= 0:
        bet, reason = False, "no Kelly edge"

    if bet:
        frac = full * fraction * (confidence / 100.0)
        frac = min(frac, cap)
    else:
        frac = 0.0

    return Stake(
        market=market, selection=selection, odds=decimal_odds,
        my_prob=round(my_prob, 4), fair_prob=round(fair_prob, 4),
        ev=round(ev, 4), edge_vs_market=round(edge, 4),
        full_kelly=round(full, 4), stake_fraction=round(frac, 4),
        stake_units=round(frac * bankroll, 2), bet=bet, reason=reason,
    )


def cap_total_exposure(stakes: list[Stake], max_exposure: float = 0.15,
                       bankroll: float = 100.0) -> list[Stake]:
    """
    Scale down all active stakes proportionally if combined exposure exceeds the
    max live-exposure cap (correlated/multiple bets shouldn't blow the bankroll).
    """
    total_frac = sum(s.stake_fraction for s in stakes if s.bet)
    if total_frac <= max_exposure or total_frac == 0:
        return stakes
    scale = max_exposure / total_frac
    for s in stakes:
        if s.bet:
            s.stake_fraction = round(s.stake_fraction * scale, 4)
            s.stake_units = round(s.stake_fraction * bankroll, 2)
            s.reason += f" (scaled ×{scale:.2f} for exposure cap)"
    return stakes


if __name__ == "__main__":
    s = size_bet("1x2", "home", my_prob=0.55, decimal_odds=2.10,
                 fair_prob=0.476, confidence=70)
    print(s)
    s2 = size_bet("1x2", "home", my_prob=0.55, decimal_odds=1.70,
                  fair_prob=0.588, confidence=70)
    print(s2)
