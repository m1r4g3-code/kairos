"""
KAIROS engine — ledger (L19) test suite.

Exercises the persistence/calibration layer in an isolated temp directory so it
never touches the real ledger. Covers the integrity bugs found in the audit:
duplicate-ID auto-versioning, multi-pick scoring, score-based O/U push settling,
corrupt-line resilience, and the Brier/ROI/CLV arithmetic.

Run:  python test_ledger.py   (exits non-zero on any failure)
"""

from __future__ import annotations

import os
import tempfile

import ledger

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def _pred(pid: str, picks: list[dict], **extra) -> dict:
    return {"id": pid, "match": "A vs B", "picks": picks, "verdict": "BET", **extra}


def run_all() -> None:
    tmp = tempfile.mkdtemp(prefix="kairos_ledger_")
    ledger.PRED_PATH = os.path.join(tmp, "predictions.jsonl")
    ledger.RES_PATH = os.path.join(tmp, "results.jsonl")

    # ── schema validation ─────────────────────────────────────────────────────
    bad = False
    try:
        ledger.log_prediction({"id": "x", "picks": []})       # empty picks
    except ValueError:
        bad = True
    check("empty picks rejected", bad)

    bad2 = False
    try:
        ledger.log_prediction({"id": "y", "picks": [{"market": "1x2"}]})  # no selection
    except ValueError:
        bad2 = True
    check("pick missing selection rejected", bad2)

    # ── duplicate-id auto-versioning (no silent overwrite) ─────────────────────
    id1 = ledger.log_prediction(_pred(
        "2026-01-01-AAA", [{"market": "1x2", "selection": "home",
                            "my_prob": 0.55, "odds": 2.10, "stake_units": 2.0}]))
    id2 = ledger.log_prediction(_pred(
        "2026-01-01-AAA", [{"market": "1x2", "selection": "away",
                            "my_prob": 0.30, "odds": 3.50, "stake_units": 1.0}]))
    check("duplicate id is versioned", id1 != id2 and id2 == "2026-01-01-AAA-2",
          f"id1={id1} id2={id2}")

    # ── multi-pick scoring + score-based settling ──────────────────────────────
    ledger.log_prediction(_pred(
        "2026-01-02-MULTI",
        [{"market": "1x2", "selection": "home", "my_prob": 0.50, "odds": 2.0,
          "stake_units": 2.0},
         {"market": "ou_2.5", "selection": "over_2.5", "my_prob": 0.55, "odds": 1.9,
          "stake_units": 1.0},
         {"market": "btts", "selection": "btts_yes", "my_prob": 0.60, "odds": 1.8,
          "stake_units": 1.0}]))
    # Final score 2-1: home win (✓), total 3 > 2.5 over (✓), both scored yes (✓).
    ledger.record_result("2026-01-02-MULTI", outcome="home", closing_odds=1.9,
                         score="2-1")

    cal = ledger.compute_calibration()
    check("all three picks scored (not just headline)", cal["n_scored_picks"] >= 3,
          f"n_scored_picks={cal['n_scored_picks']}")

    # log_prediction auto-versions, so a genuine duplicate only arises from a manual
    # edit. Inject one raw and confirm compute_calibration *reports* it (no silent
    # overwrite — the headline pick is scored, the collision is surfaced).
    import json as _json
    with open(ledger.PRED_PATH, "a", encoding="utf-8") as f:
        f.write(_json.dumps(_pred("2026-01-02-MULTI",
                [{"market": "1x2", "selection": "away", "my_prob": 0.2,
                  "odds": 5.0, "stake_units": 0.0}])) + "\n")
    cal_dup = ledger.compute_calibration()
    check("duplicate ids reported", "2026-01-02-MULTI" in cal_dup["duplicate_ids"],
          f"dups={cal_dup['duplicate_ids']}")

    # ── O/U push is voided, not counted as a loss ──────────────────────────────
    ledger.log_prediction(_pred(
        "2026-01-03-PUSH",
        [{"market": "ou_3.0", "selection": "over_3.0", "my_prob": 0.5, "odds": 2.0,
          "stake_units": 1.0}]))
    ledger.record_result("2026-01-03-PUSH", outcome=None, score="2-1")  # total 3 == line
    won = ledger._pick_won(
        {"market": "ou_3.0", "selection": "over_3.0"}, {"score": "2-1"})
    check("whole-line exact total is a push (void)", won is None, f"won={won}")

    # ── ROI / profit arithmetic on a clean settled bet ──────────────────────────
    # MULTI: home 2.0@2.0 win -> +2.0; over 1.0@1.9 win -> +0.9; btts 1.0@1.8 win -> +0.8
    # AAA(-? unsettled) — only MULTI settled with stakes -> profit = 3.7 on 4.0 staked
    check("profit computed from all winning picks",
          abs(cal["profit_units"] - 3.7) < 1e-6, f"profit={cal['profit_units']}")
    check("hit_rate = 1.0 when all settled picks won", cal["hit_rate"] == 1.0,
          f"hit_rate={cal['hit_rate']}")

    # ── CLV: headline odds 1.9 vs closing 1.9 -> 0 ─────────────────────────────
    check("CLV computed for headline pick", cal["avg_clv"] is not None)

    # ── corrupt line resilience ────────────────────────────────────────────────
    with open(ledger.PRED_PATH, "a", encoding="utf-8") as f:
        f.write("this is not json\n")
    cal2 = ledger.compute_calibration()
    check("corrupt line skipped, not fatal", cal2["bad_lines"]["predictions"] >= 1,
          f"bad_lines={cal2['bad_lines']}")

    # ── pending list ────────────────────────────────────────────────────────────
    pend_ids = {p["id"] for p in ledger.pending_predictions()}
    check("settled prediction not pending", "2026-01-02-MULTI" not in pend_ids)
    check("unsettled prediction is pending", "2026-01-01-AAA" in pend_ids)

    print("\n" + ("ALL LEDGER TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
