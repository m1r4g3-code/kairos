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
  "devig_method": "proportional",                           # OR "power" (favourite-longshot bias)
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

import constants
import poisson
import elo as elo_mod
import monte_carlo
import market as market_mod
import kelly


def _validate_spec(spec: dict) -> None:
    """Fail fast with a clear message on a malformed spec (boundary validation)."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")
    conf = spec.get("confidence", 60)
    if not (0 <= float(conf) <= 100):
        raise ValueError(f"confidence must be in [0, 100], got {conf}")
    if float(spec.get("bankroll", 100)) <= 0:
        raise ValueError("bankroll must be > 0")
    if "lambdas" in spec:
        lam = spec["lambdas"]
        if float(lam.get("home", 0)) <= 0 or float(lam.get("away", 0)) <= 0:
            raise ValueError(f"lambdas must be > 0, got {lam}")
    for mkt_key, mkt_odds in spec.get("odds", {}).items():
        if not isinstance(mkt_odds, dict):
            raise ValueError(f"odds['{mkt_key}'] must be an object of selection->price")
        for sel, price in mkt_odds.items():
            if float(price) <= 1.0:
                raise ValueError(
                    f"decimal odds must be > 1.0, got {price} for {mkt_key}.{sel}"
                )


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


def _ev_for(lam_h: float, lam_a: float, rho: float,
            market_key: str, selection: str, decimal_odds: float) -> float | None:
    """Recompute EV for one selection under a (perturbed) pair of lambdas."""
    dist = poisson.full_markets(lam_h, lam_a, rho)
    my_p = _my_prob_for(market_key, selection, dist)
    if my_p is None:
        return None
    return kelly.expected_value(my_p, decimal_odds)


def _sensitivity(lam_h: float, lam_a: float, rho: float, best_bet: dict,
                 perturb: float = constants.SENSITIVITY_PERTURB) -> dict:
    """
    Fragility test for the headline bet: re-price it under a grid of ±`perturb`
    lambda shifts. If the bet's EV drops below the min-edge gate under ANY plausible
    nudge, the "value" is an artifact of soft inputs, not a robust edge → flag it.
    This is the antidote to false precision (laundering a guessed lambda into a
    6-decimal probability).
    """
    factors = (1.0 - perturb, 1.0, 1.0 + perturb)
    evs: list[float] = []
    for fh in factors:
        for fa in factors:
            ev = _ev_for(round(lam_h * fh, 4), round(lam_a * fa, 4), rho,
                         best_bet["market"], best_bet["selection"], best_bet["odds"])
            if ev is not None:
                evs.append(ev)
    min_ev, max_ev = min(evs), max(evs)
    robust = min_ev >= constants.MIN_EDGE
    return {
        "perturb_pct": round(perturb * 100, 1),
        "ev_min": round(min_ev, 4),
        "ev_max": round(max_ev, 4),
        "robust": robust,
        "note": ("edge survives +/-{:.0f}% lambda shift".format(perturb * 100) if robust
                 else "FRAGILE: edge disappears under a +/-{:.0f}% lambda shift -- "
                      "treat as speculative, not a value bet".format(perturb * 100)),
    }


def build_prediction(spec: dict) -> dict:
    """Run the full engine on a spec and return the distribution + value table."""
    _validate_spec(spec)
    lam_h, lam_a = _resolve_lambdas(spec)

    # Bounded qualitative modifiers (my judgment, applied to lambdas).
    mods = spec.get("modifiers", {})
    lam_h *= mods.get("lam_home_mult", 1.0)
    lam_a *= mods.get("lam_away_mult", 1.0)
    lam_h, lam_a = round(lam_h, 4), round(lam_a, 4)

    rho = spec.get("rho", constants.DEFAULT_RHO)
    devig_method = spec.get("devig_method", "proportional")
    confidence = float(spec.get("confidence", 60))
    bankroll = float(spec.get("bankroll", 100))

    # Analytic distribution (exact).
    dist = poisson.full_markets(lam_h, lam_a, rho)

    # Monte Carlo cross-check; lambda uncertainty scales inversely with confidence.
    sigma = max(0.0, (100 - confidence) / 100.0) * constants.SIGMA_SCALER
    mc = monte_carlo.simulate(lam_h, lam_a, n=constants.MC_DEFAULT_N,
                              lambda_sigma=sigma, seed=constants.MC_SEED)

    # Value table: for every market with odds, de-vig and size each selection.
    # Any selection the analytic engine does not model is recorded explicitly in
    # `skipped_markets` rather than silently dropped (no hidden data loss).
    odds = spec.get("odds", {})
    value_table: list[dict] = []
    stakes: list[kelly.Stake] = []
    skipped: list[dict] = []

    for mkt_key, mkt_odds in odds.items():
        view = market_mod.market_view(mkt_odds, method=devig_method)
        for sel in view["labels"]:
            my_p = _my_prob_for(mkt_key, sel, dist)
            if my_p is None:
                skipped.append({"market": mkt_key, "selection": sel,
                                "odds": mkt_odds[sel],
                                "reason": "engine does not model this market/line"})
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
    best_bet = value_bets[0] if value_bets else None
    sensitivity = _sensitivity(lam_h, lam_a, rho, best_bet) if best_bet else None

    # If the headline value bet is fragile, downgrade the verdict honestly.
    if best_bet and sensitivity and not sensitivity["robust"]:
        verdict = "SPECULATIVE -- value is fragile to input assumptions"
    elif value_bets:
        verdict = "BET"
    else:
        verdict = "PASS -- no value"

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
        "skipped_markets": skipped,
        "sensitivity": sensitivity,
        "verdict": verdict,
        "best_bet": best_bet,
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
