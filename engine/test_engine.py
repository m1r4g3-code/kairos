"""
KAIROS engine — test suite.

Deterministic assertions on the highest-risk module. Run:
    python test_engine.py
Exits non-zero on any failure.
"""

from __future__ import annotations

import math

import poisson
import elo as elo_mod
import monte_carlo
import market as market_mod
import kelly
from run import build_prediction

TOL = 1e-6
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


# ── market.py ────────────────────────────────────────────────────────────────
def test_market() -> None:
    odds = {"home": 2.10, "draw": 3.40, "away": 3.60}
    v = market_mod.market_view(odds)
    s = sum(v["fair_prob"].values())
    check("devig sums to 1.0", abs(s - 1.0) < TOL, f"sum={s}")
    check("overround positive & sane", 0.02 < v["overround"] < 0.12, f"or={v['overround']}")
    # de-vigged favorite prob < raw implied (vig removed)
    check("devig shrinks raw implied",
          v["fair_prob"]["home"] < v["implied_raw"]["home"])
    # power method also sums to 1, and every prob is a valid probability
    p = market_mod.devig_power([2.10, 3.40, 3.60])
    check("power devig sums to 1.0", abs(sum(p) - 1.0) < TOL)
    check("power devig probs in (0,1)", all(0.0 < x < 1.0 for x in p))
    # power de-vig reachable through market_view (was previously dead code)
    vp = market_mod.market_view(odds, method="power")
    check("market_view power method sums to 1.0",
          abs(sum(vp["fair_prob"].values()) - 1.0) < TOL)


# ── poisson.py ───────────────────────────────────────────────────────────────
def test_poisson() -> None:
    m = poisson.score_matrix(1.6, 1.1)
    total = sum(sum(row) for row in m)
    check("score matrix sums to 1.0", abs(total - 1.0) < TOL, f"sum={total}")

    o = poisson.outcome_1x2(m)
    check("1X2 sums to 1.0", abs(sum(o.values()) - 1.0) < TOL)
    check("home favored when lam_home > lam_away", o["home"] > o["away"])

    ou = poisson.over_under(m, 2.5)
    check("O/U sums to 1.0", abs(sum(ou.values()) - 1.0) < TOL)

    bt = poisson.btts(m)
    check("BTTS sums to 1.0", abs(sum(bt.values()) - 1.0) < TOL)

    # Dixon-Coles must boost the 0-0 cell vs independent Poisson (rho<0).
    indep_00 = poisson.poisson_pmf(0, 1.6) * poisson.poisson_pmf(0, 1.1)
    dc_00 = poisson.score_matrix(1.6, 1.1, rho=-0.10)[0][0]
    check("Dixon-Coles boosts 0-0 (rho<0)", dc_00 > indep_00,
          f"dc={dc_00:.4f} indep={indep_00:.4f}")

    # Draw probability should land in the sane football band.
    check("draw prob in 18-34% band", 0.18 < o["draw"] < 0.34, f"draw={o['draw']}")

    # Expected goals read back off the matrix ~= input lambdas.
    eh, ea = poisson.expected_goals(m)
    check("expected goals ~= lambdas", abs(eh - 1.6) < 0.05 and abs(ea - 1.1) < 0.05,
          f"eh={eh} ea={ea}")

    # Symmetry: equal lambdas => equal home/away win prob.
    sym = poisson.outcome_1x2(poisson.score_matrix(1.3, 1.3))
    check("equal lambdas => symmetric 1X2", abs(sym["home"] - sym["away"]) < TOL)

    # Non-negativity: NO cell may be negative (normalization alone wouldn't catch this).
    m2 = poisson.score_matrix(2.4, 2.1, rho=-0.10)
    check("no negative probability cells", all(p >= 0 for row in m2 for p in row))

    # Out-of-band rho must be rejected, not silently produce a bad distribution.
    bad_rho = False
    try:
        poisson.score_matrix(1.5, 1.2, rho=0.9)
    except ValueError:
        bad_rho = True
    check("out-of-band rho raises", bad_rho)

    # Whole-number O/U: exact total is a PUSH, not an under. over+under+push == 1.
    ou_whole = poisson.over_under(m, 2.0)
    check("whole-line O/U exposes a push", "push_2.0" in ou_whole)
    check("over+under+push sums to 1.0",
          abs(sum(ou_whole.values()) - 1.0) < TOL, f"sum={sum(ou_whole.values())}")
    # Half-line stays two-way (no push key).
    ou_half = poisson.over_under(m, 2.5)
    check("half-line O/U has no push key", "push_2.5" not in ou_half)


# ── elo.py ───────────────────────────────────────────────────────────────────
def test_elo() -> None:
    check("equal ratings + HFA => home expected > 0.5",
          elo_mod.elo_expected_score(1500, 1500) > 0.5)
    lh, la = elo_mod.elo_to_lambdas(1600, 1500, total_goals=2.8)
    check("elo lambdas sum to total_goals", abs((lh + la) - 2.8) < 1e-3,
          f"sum={lh+la}")
    check("higher-rated home gets higher lambda", lh > la)
    lh2, la2 = elo_mod.strengths_to_lambdas(1.2, 0.9, 1.0, 1.1, home_mult=1.15)
    check("strengths produce positive lambdas", lh2 > 0 and la2 > 0)


# ── monte_carlo.py ───────────────────────────────────────────────────────────
def test_monte_carlo() -> None:
    analytic = poisson.outcome_1x2(poisson.score_matrix(1.6, 1.1, rho=0.0))
    mc = monte_carlo.simulate(1.6, 1.1, n=60_000, seed=1)["1x2"]
    # With rho=0 the analytic (independent) and MC should agree within sampling error.
    for k in ("home", "draw", "away"):
        check(f"MC ~= analytic ({k})", abs(mc[k] - analytic[k]) < 0.02,
              f"mc={mc[k]} analytic={analytic[k]}")
    # lambda uncertainty should pull extreme probs toward the middle (fatter tails).
    base = monte_carlo.simulate(2.2, 0.6, n=60_000, seed=2)["1x2"]["home"]
    noisy = monte_carlo.simulate(2.2, 0.6, n=60_000, lambda_sigma=0.4, seed=2)["1x2"]["home"]
    check("lambda uncertainty softens a strong favorite", noisy < base,
          f"base={base} noisy={noisy}")


# ── kelly.py ─────────────────────────────────────────────────────────────────
def test_kelly() -> None:
    check("EV positive when prob*odds>1", kelly.expected_value(0.55, 2.10) > 0)
    check("EV negative when prob*odds<1", kelly.expected_value(0.55, 1.70) < 0)
    check("no Kelly when no edge", kelly.kelly_fraction(0.55, 1.70) == 0.0)

    s = kelly.size_bet("1x2", "home", 0.55, 2.10, 0.476, confidence=70)
    check("value bet flagged", s.bet)
    check("stake within cap", s.stake_fraction <= kelly.DEFAULT_CAP + TOL,
          f"frac={s.stake_fraction}")
    check("stake is fractional Kelly", s.stake_fraction < s.full_kelly)

    s2 = kelly.size_bet("1x2", "home", 0.55, 1.70, 0.588, confidence=70)
    check("negative-edge bet rejected", not s2.bet and s2.stake_units == 0)

    s3 = kelly.size_bet("1x2", "home", 0.55, 2.10, 0.476, confidence=30)
    check("low confidence => pass (floor)", not s3.bet)

    # huge edge should still be capped
    s4 = kelly.size_bet("1x2", "home", 0.90, 5.00, 0.30, confidence=95)
    check("huge edge still capped at 5%", s4.stake_fraction <= kelly.DEFAULT_CAP + TOL,
          f"frac={s4.stake_fraction}")

    # Total-exposure cap: several big bets must be scaled to <= MAX_EXPOSURE combined.
    bets = [kelly.size_bet("1x2", str(i), 0.90, 5.00, 0.30, confidence=95)
            for i in range(5)]
    capped = kelly.cap_total_exposure(bets, bankroll=100.0)
    total = sum(s.stake_fraction for s in capped if s.bet)
    check("combined exposure capped", total <= kelly.constants.MAX_EXPOSURE + TOL,
          f"total={total}")


# ── run.py (end-to-end) ──────────────────────────────────────────────────────
def test_run_value() -> None:
    # Spec with deliberately generous home odds => should surface a value bet.
    spec = {
        "match": "Test Home vs Test Away", "league": "Premier League",
        "lambdas": {"home": 1.9, "away": 0.9}, "confidence": 75, "bankroll": 100,
        "odds": {"1x2": {"home": 2.50, "draw": 3.40, "away": 3.20}},
    }
    res = build_prediction(spec)
    check("run produces a verdict",
          res["verdict"] in ("BET", "SPECULATIVE -- value is fragile to input assumptions",
                             "PASS -- no value"))
    check("run finds value on underpriced home", res["best_bet"] is not None,
          f"verdict={res['verdict']}")
    if res["best_bet"]:
        check("best bet stake within cap", res["best_bet"]["stake_units"] <= 5.0 + TOL)
    # Sensitivity block is present whenever there is a best bet.
    check("sensitivity reported for a value bet", res["sensitivity"] is not None)
    # A robust strong edge should survive the perturbation grid.
    check("strong edge flagged robust", res["sensitivity"]["robust"],
          f"sens={res['sensitivity']}")


def test_run_skipped_and_validation() -> None:
    # An unmodelled market/line must be surfaced, not silently dropped.
    spec = {
        "match": "X vs Y", "league": "Test", "lambdas": {"home": 1.4, "away": 1.2},
        "confidence": 60, "bankroll": 100,
        "odds": {"1x2": {"home": 2.4, "draw": 3.3, "away": 3.0},
                 "ou_4.5": {"over_4.5": 5.0, "under_4.5": 1.18}},
    }
    res = build_prediction(spec)
    check("unmodelled market surfaced in skipped_markets",
          any(s["market"] == "ou_4.5" for s in res["skipped_markets"]),
          f"skipped={res['skipped_markets']}")

    # Invalid odds (<=1.0) must be rejected at the boundary.
    bad = False
    try:
        build_prediction({"lambdas": {"home": 1.2, "away": 1.0}, "confidence": 60,
                          "odds": {"1x2": {"home": 1.0, "draw": 3.3, "away": 3.0}}})
    except ValueError:
        bad = True
    check("invalid odds rejected", bad)

    # Out-of-range confidence rejected.
    bad2 = False
    try:
        build_prediction({"lambdas": {"home": 1.2, "away": 1.0}, "confidence": 150,
                          "odds": {"1x2": {"home": 2.0, "draw": 3.3, "away": 4.0}}})
    except ValueError:
        bad2 = True
    check("out-of-range confidence rejected", bad2)


def test_run_pass() -> None:
    # Odds set to roughly the model's own fair prices + a normal vig => no edge => PASS.
    # First read what the model thinks, then price every selection at (fair_prob)^-1
    # shortened by a 6% margin so nothing clears the +3% EV gate.
    lam_h, lam_a = 1.4, 1.3
    o = poisson.outcome_1x2(poisson.score_matrix(lam_h, lam_a))
    margin = 1.06
    fair_odds = {k: round(1.0 / (o[k] * margin), 2) for k in o}
    spec = {
        "match": "Test A vs Test B", "league": "Premier League",
        "lambdas": {"home": lam_h, "away": lam_a}, "confidence": 70, "bankroll": 100,
        "odds": {"1x2": fair_odds},
    }
    res = build_prediction(spec)
    check("run returns PASS when no edge beats the price",
          res["verdict"] == "PASS -- no value" or res["verdict"].startswith("PASS"),
          f"verdict={res['verdict']} odds={fair_odds}")


def test_report() -> None:
    import report

    # Overpriced short favourite => flagged as a trap.
    trap_spec = {"match": "Trap FC v Minnow", "lambdas": {"home": 0.6, "away": 2.2},
                 "confidence": 49, "odds": {"1x2": {"home": 11.0, "draw": 6.8, "away": 1.16}}}
    s = report.summarize(build_prediction(trap_spec))
    check("favourite is the shortest price", abs(s["fav"]["odds"] - 1.16) < TOL)
    check("overpriced short favourite flagged as trap", s["trap"], f"gap={s['gap']}")

    # A genuine robust value bet renders under 'VALUE BETS TO PLACE'.
    val_spec = {"match": "Value FC v Weak", "lambdas": {"home": 1.9, "away": 0.9},
                "confidence": 75, "odds": {"1x2": {"home": 2.5, "draw": 3.4, "away": 3.2}}}
    card = report.render_card([build_prediction(val_spec)])
    check("robust value surfaced in card", "BET THESE" in card
          and "Value FC" in card)
    # team name + venue label rendered (no raw 'home'/'away' tokens)
    check("renders team name with venue", "Value FC (HOME)" in card, card)
    # A fairly-priced game is not a trap and yields no value.
    fair_spec = {"match": "Fair A v Fair B", "lambdas": {"home": 1.3, "away": 1.25},
                 "confidence": 60, "odds": {"1x2": {"home": 2.6, "draw": 3.2, "away": 2.7}}}
    sf = report.summarize(build_prediction(fair_spec))
    check("fairly-priced favourite not a trap", not sf["trap"])


def run_all() -> None:
    for fn in (test_market, test_poisson, test_elo, test_monte_carlo,
               test_kelly, test_run_value, test_run_pass,
               test_run_skipped_and_validation, test_report):
        fn()
    print("\n" + ("ALL TESTS PASSED" if not _failures
                   else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
