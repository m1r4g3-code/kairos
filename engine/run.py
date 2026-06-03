"""
KAIROS engine — orchestrator (the single entry point).

Takes a match spec (dict or JSON file/stdin), computes the calibrated probability
distribution, and produces a value table vs the bookmaker odds. This is what the
predict protocol calls after I (Claude) have built the spec from the screenshot +
enrichment + bounded qualitative modifiers.

Usage:
    python run.py spec.json
    python run.py < spec.json
    (or import build_prediction directly)

Pure stdlib. No API keys, no network, no bet placement.

──────────────────────────────────────────────────────────────────────────────
SPEC SCHEMA (all of lambdas / strengths / elo optional — pick one source):
{
  "match": "Arsenal vs Chelsea", "league": "Premier League",
  "lambdas":   {"home": 1.6, "away": 1.1},                  # OR
  "strengths": {"att_home":1.2,"def_home":0.9,"att_away":1.0,"def_away":1.1,
                "league_home_avg":1.55,"league_away_avg":1.25,"home_mult":1.15}, # OR
  "elo":       {"home":1600,"away":1500,"total_goals":2.8,"home_advantage":65},
  "rho": -0.10,
  "modifiers": {"lam_home_mult":1.05,"lam_away_mult":0.95,"note":"home press edge, away CB out"},
  "confidence": 68,
  "bankroll": 100,
  "odds": {                                                 # from the screenshot
     "1x2":  {"home":2.10,"draw":3.40,"away":3.60},
     "ou_2.5":{"over_2.5":1.95,"under_2.5":1.85},
     "btts": {"btts_yes":1.80,"btts_no":1.95}
  }
}
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import sys

import poisson
import elo as elo_mod
import monte_carlo
import market as market_mod
import kelly


def _resolve_lambdas(spec: dict) -> tuple[float, float]:
    """Pick the lambda source in priority order: direct > strengths > elo."""
    if "lambdas" in spec:
        return float(spec["lambdas"]["home"]), float(spec["lambdas"]["away"])
    if "strengths" in spec:
        s = spec["strengths"]
        return elo_mod.strengths_to_lambdas(
            s["att_home"], s["def_home"], s["att_away"], s["def_away"],
            s.get("league_home_avg", 1.50), s.get("league_away_avg", 1.20),
            s.get("home_mult", 1.0),
        )
    if "elo" in spec:
        e = spec["elo"]
        return elo_mod.elo_to_lambdas(
            e["home"], e["away"], e.get("total_goals", 2.7),
            e.get("home_advantage", 65.0),
        )
    raise ValueError("spec must contain one of: lambdas, strengths, elo")


# Markets where higher model prob means the bet is on that selection.
# Maps market key -> {selection_label: probability_key_in_distribution}
def _my_prob_for(market_key: str, selection: str, dist: dict) -> float | None:
    """Look up my model probability for a given market+selection."""
    if market_key == "1x2":
        return dist["1x2"].get(selection)
    if market_key.startswith("ou_"):
        return dist.get(market_key, {}).get(selection)
    if market_key == "btts":
        return dist["btts"].get(selection)
    return None


def build_prediction(spec: dict) -> dict:
    """Run the full engine on a spec and return the distribution + value table."""
    lam_h, lam_a = _resolve_lambdas(spec)

    # Bounded qualitative modifiers (my judgment, applied to lambdas).
    mods = spec.get("modifiers", {})
    lam_h *= mods.get("lam_home_mult", 1.0)
    lam_a *= mods.get("lam_away_mult", 1.0)
    lam_h, lam_a = round(lam_h, 4), round(lam_a, 4)

    rho = spec.get("rho", -0.10)
    confidence = float(spec.get("confidence", 60))
    bankroll = float(spec.get("bankroll", 100))

    # Analytic distribution (exact).
    dist = poisson.full_markets(lam_h, lam_a, rho)

    # Monte Carlo cross-check; lambda uncertainty scales inversely with confidence.
    sigma = max(0.0, (100 - confidence) / 100.0) * 0.35
    mc = monte_carlo.simulate(lam_h, lam_a, n=30_000, lambda_sigma=sigma, seed=7)

    # Value table: for every market with odds, de-vig and size each selection.
    odds = spec.get("odds", {})
    value_table: list[dict] = []
    stakes: list[kelly.Stake] = []

    for mkt_key, mkt_odds in odds.items():
        view = market_mod.market_view(mkt_odds)
        for sel in view["labels"]:
            my_p = _my_prob_for(mkt_key, sel, dist)
            if my_p is None:
                continue
            fair = view["fair_prob"][sel]
            st = kelly.size_bet(
                market=mkt_key, selection=sel, my_prob=my_p,
                decimal_odds=mkt_odds[sel], fair_prob=fair,
                confidence=confidence, bankroll=bankroll,
            )
            stakes.append(st)

    stakes = kelly.cap_total_exposure(stakes, bankroll=bankroll)
    for st in stakes:
        value_table.append({
            "market": st.market, "selection": st.selection, "odds": st.odds,
            "my_prob": st.my_prob, "fair_prob": st.fair_prob,
            "ev": st.ev, "edge_vs_market": st.edge_vs_market,
            "stake_units": st.stake_units, "bet": st.bet, "reason": st.reason,
        })
    value_table.sort(key=lambda r: (r["bet"], r["ev"]), reverse=True)

    value_bets = [r for r in value_table if r["bet"]]
    return {
        "match": spec.get("match", "?"),
        "league": spec.get("league", "?"),
        "lambdas": {"home": lam_h, "away": lam_a},
        "modifier_note": mods.get("note", ""),
        "confidence": confidence,
        "distribution": dist,
        "monte_carlo_check": {"1x2": mc["1x2"], "ou_2.5": mc["ou_2.5"],
                              "btts": mc["btts"]},
        "value_table": value_table,
        "verdict": "BET" if value_bets else "PASS — no value",
        "best_bet": value_bets[0] if value_bets else None,
    }


def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            spec = json.load(f)
    else:
        spec = json.load(sys.stdin)
    print(json.dumps(build_prediction(spec), indent=2))


if __name__ == "__main__":
    main()
