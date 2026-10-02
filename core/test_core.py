"""
KAIROS — core package tests (offline).

Run:  python core/test_core.py   (exits non-zero on any failure)

Checks that the core package works on its own, with no football code loaded,
on a market that is not football: a yes/no prediction-market contract.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import devig, ledger, metrics, staking  # noqa: E402

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def test_no_football_imports() -> None:
    code = ("import sys; sys.path.insert(0, r'%s'); "
            "from core import staking, devig, ledger, metrics, runlog; "
            "bad = {'poisson','elo','edge','run','derive','fd_data','strategies','odds_api',"
            "'constants','config','settle'} & set(sys.modules); "
            "print(sorted(bad)); raise SystemExit(1 if bad else 0)") % ROOT
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    check("core imports no football or engine module", out.returncode == 0, out.stdout.strip())


def test_staking_and_devig() -> None:
    fair = devig.devig_power([1.80, 2.10])              # a two-way contract with a margin
    check("two-way de-vig sums to 1", abs(sum(fair) - 1.0) < 1e-9)
    s = staking.size_bet("binary", "yes", my_prob=0.60, decimal_odds=1.90,
                         fair_prob=fair[0], confidence=80)
    check("a positive-EV contract is sized and capped",
          s.bet and 0 < s.stake_fraction <= staking.DEFAULT_CAP)
    check("the staking defaults are defined in core",
          (staking.DEFAULT_FRACTION, staking.DEFAULT_CAP, staking.MIN_EDGE,
           staking.MAX_EXPOSURE) == (0.25, 0.05, 0.03, 0.15))
    two = [staking.size_bet("binary", str(i), 0.9, 5.0, 0.3, confidence=95) for i in range(2)]
    check("one event is one position",
          abs(sum(b.stake_fraction for b in staking.cap_match_exposure(two)) - 0.05) < 1e-3)


def test_ledger_with_generic_settlement() -> None:
    tmp = tempfile.mkdtemp(prefix="kairos_core_")
    ledger.configure(os.path.join(tmp, "p.jsonl"), os.path.join(tmp, "r.jsonl"),
                     settler=ledger.default_settle)
    ledger.log_prediction({"id": "pm-1", "picks": [
        {"market": "binary", "selection": "yes", "my_prob": 0.6, "raw_prob": 0.55,
         "odds": 1.9, "stake_units": 2.0}]})
    ledger.log_prediction({"id": "pm-2", "picks": [
        {"market": "binary", "selection": "yes", "my_prob": 0.3, "odds": 3.5, "stake_units": 1.0}]})
    ledger.record_result("pm-1", outcome="yes", closing_fair_prob=0.58)
    ledger.record_result("pm-2", outcome="lose")
    cal = ledger.compute_calibration()
    check("generic settlement: selection match and explicit lose",
          abs(cal["profit_units"] - (2.0 * 0.9 - 1.0)) < 1e-9 and cal["n_scored_picks"] == 2,
          str(cal["profit_units"]))
    check("fair CLV from the closing probability",
          abs(cal["avg_clv_fair"] - (1.9 * 0.58 - 1.0)) < 1e-4, str(cal["avg_clv_fair"]))
    check("raw against adjusted probability is scored", cal["judgment"]["n"] == 1)
    check("football markets are not understood by the generic settler",
          ledger.default_settle({"market": "ou_2.5", "selection": "over_2.5"},
                                {"score": "3-1"}) is None)

    def my_settler(pick, result):
        return result.get("resolved") == pick["selection"]
    ledger.set_settler(my_settler)
    check("another agent can install its own settler",
          ledger._pick_won({"selection": "no"}, {"resolved": "no"}) is True)
    ledger.set_settler(ledger.default_settle)


def test_metrics() -> None:
    s = metrics.forecast_summary([((0.7, 0.3), 0)] * 7 + [((0.7, 0.3), 1)] * 3)
    check("metrics score a two-outcome forecast", s["n"] == 10 and s["ece"] < 1e-9)
    b = metrics.bet_summary([{"cluster": i, "stake": 1.0, "profit": 0.5, "clv": 0.01, "odds": 1.5}
                             for i in range(10)], n_boot=200)
    check("bet summary works on any bets", abs(b["roi"] - 0.5) < 1e-12)


def run_all() -> None:
    for fn in (test_no_football_imports, test_staking_and_devig,
               test_ledger_with_generic_settlement, test_metrics):
        fn()
    print("\n" + ("ALL CORE TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
