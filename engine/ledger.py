"""
KAIROS engine — Feedback loop (L19).

Concrete, low-friction tooling for the calibration loop:
  - log_prediction(record)            append a pick to ledger/predictions.jsonl
  - record_result(id, result, line)   append the outcome to ledger/results.jsonl
  - compute_calibration()             join both, compute Brier / hit-rate / ROI / CLV
                                      + calibration buckets, and return a summary dict

Pure stdlib. Paths resolved relative to the Kairos root (parent of engine/).

CLI:
    python ledger.py stats          # print current calibration summary
    python ledger.py result <id> <home|draw|away> <closing_odds_of_pick>
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
PRED_PATH = os.path.join(_ROOT, "ledger", "predictions.jsonl")
RES_PATH = os.path.join(_ROOT, "ledger", "results.jsonl")

BUCKETS = [(0.70, 1.01), (0.55, 0.70), (0.40, 0.55), (0.25, 0.40), (0.0, 0.25)]


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def log_prediction(record: dict) -> None:
    """Append a prediction record (shape documented in protocols/predict.md)."""
    with open(PRED_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def record_result(pred_id: str, outcome: str, closing_odds: float | None = None) -> None:
    """
    Append an actual result for a logged prediction.
    outcome: the realized 1X2 result ("home"/"draw"/"away") — or for non-1X2 picks,
             "win"/"lose" for the staked selection.
    closing_odds: the closing price of the picked selection (for CLV).
    """
    rec = {"id": pred_id, "outcome": outcome, "closing_odds": closing_odds}
    with open(RES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def compute_calibration() -> dict:
    """Join predictions+results and compute the scorecard."""
    preds = {p["id"]: p for p in _read_jsonl(PRED_PATH) if "id" in p}
    results = _read_jsonl(RES_PATH)

    n_pred = len(preds)
    brier_terms: list[float] = []
    staked = won = 0
    profit = 0.0
    clv_terms: list[float] = []
    bucket_hits = {b: [0, 0] for b in BUCKETS}  # band -> [wins, n]
    n_res = 0

    for r in results:
        p = preds.get(r["id"])
        if not p or not p.get("picks"):
            continue
        n_res += 1
        pick = p["picks"][0]  # headline pick
        my_prob = pick.get("my_prob")
        odds = pick.get("odds")
        stake = pick.get("stake_units", 0.0)
        outcome = r.get("outcome")

        # Did the staked selection win?
        sel = pick.get("selection")
        win = (outcome == sel) or (outcome == "win")

        # Brier (binary on the staked selection)
        if my_prob is not None:
            brier_terms.append((my_prob - (1.0 if win else 0.0)) ** 2)
            for b in BUCKETS:
                if b[0] <= my_prob < b[1]:
                    bucket_hits[b][1] += 1
                    if win:
                        bucket_hits[b][0] += 1

        # ROI
        if stake > 0:
            staked += 1
            if win:
                won += 1
                profit += stake * (odds - 1.0)
            else:
                profit -= stake

        # CLV: did we beat the closing line? (our odds higher = positive CLV)
        cl = r.get("closing_odds")
        if cl and odds:
            clv_terms.append(odds / cl - 1.0)

    total_staked = sum(
        preds[r["id"]]["picks"][0].get("stake_units", 0.0)
        for r in results if r["id"] in preds and preds[r["id"]].get("picks")
        and preds[r["id"]]["picks"][0].get("stake_units", 0.0) > 0
    )

    return {
        "predictions_logged": n_pred,
        "results_recorded": n_res,
        "brier": round(sum(brier_terms) / len(brier_terms), 4) if brier_terms else None,
        "hit_rate": round(won / staked, 4) if staked else None,
        "roi": round(profit / total_staked, 4) if total_staked else None,
        "profit_units": round(profit, 2),
        "avg_clv": round(sum(clv_terms) / len(clv_terms), 4) if clv_terms else None,
        "buckets": {
            f"{int(b[0]*100)}-{int(b[1]*100)}%":
                {"hit_rate": round(h[0] / h[1], 3) if h[1] else None, "n": h[1]}
            for b, h in bucket_hits.items()
        },
    }


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "result" and len(sys.argv) >= 4:
        pid, outcome = sys.argv[2], sys.argv[3]
        cl = float(sys.argv[4]) if len(sys.argv) >= 5 else None
        record_result(pid, outcome, cl)
        print(f"Recorded result for {pid}: {outcome} (closing {cl})")
        return
    print(json.dumps(compute_calibration(), indent=2))


if __name__ == "__main__":
    main()
