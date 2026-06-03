"""
KAIROS engine — Feedback loop (L19).

Concrete, low-friction tooling for the calibration loop:
  - log_prediction(record)            append a pick to ledger/predictions.jsonl
  - record_result(id, ...)            append the outcome to ledger/results.jsonl
  - compute_calibration()             join both, compute Brier / hit-rate / ROI / CLV
                                      + calibration buckets, and return a summary dict
  - pending_predictions()             list logged predictions still awaiting a result

Pure stdlib. Paths resolved relative to the Kairos root (parent of engine/).

Integrity properties (hard-won from the audit):
  * append writes are flushed + fsync'd (durability),
  * a corrupt JSONL line is skipped and counted, never crashes a read,
  * predictions are schema-validated before write,
  * duplicate IDs are auto-versioned at write time (no silent overwrite),
  * EVERY pick in a record is scored, not just the headline (multi-pick safe),
  * picks are settled from the final score when available (handles O/U pushes).

CLI:
    python ledger.py stats                              # calibration summary
    python ledger.py pending                            # predictions awaiting results
    python ledger.py result <id> <outcome> [closing] [score]
        outcome : home|draw|away  (or win|lose for a non-1x2 single pick)
        closing : closing decimal odds of the headline pick (for CLV)  [optional]
        score   : final score "h-a" e.g. 2-1 (settles O/U & BTTS exactly) [optional]
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
PRED_PATH = os.path.join(_ROOT, "ledger", "predictions.jsonl")
RES_PATH = os.path.join(_ROOT, "ledger", "results.jsonl")

BUCKETS = [(0.70, 1.01), (0.55, 0.70), (0.40, 0.55), (0.25, 0.40), (0.0, 0.25)]


# ── IO (resilient + durable) ──────────────────────────────────────────────────

def _read_jsonl(path: str) -> tuple[list[dict], int]:
    """
    Read a JSONL file. Returns (records, bad_line_count). A malformed line is
    skipped and counted rather than taking down the whole read.
    """
    records: list[dict] = []
    bad = 0
    if not os.path.exists(path):
        return records, bad
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return records, bad


def _append_jsonl(path: str, record: dict) -> None:
    """Append one record and fsync so a crash can't leave a torn write."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


# ── Write path ─────────────────────────────────────────────────────────────────

def _validate_prediction(record: dict) -> None:
    """Reject a structurally invalid prediction before it pollutes the ledger."""
    if "id" not in record or not record["id"]:
        raise ValueError("prediction record needs a non-empty 'id'")
    picks = record.get("picks")
    if not isinstance(picks, list) or not picks:
        raise ValueError(f"prediction {record['id']} needs a non-empty 'picks' list")
    for i, pick in enumerate(picks):
        for key in ("market", "selection"):
            if key not in pick:
                raise ValueError(f"pick #{i} in {record['id']} missing '{key}'")


def log_prediction(record: dict) -> str:
    """
    Append a prediction. Validates the schema, and if the id already exists it is
    auto-versioned (`<id>-2`, `-3`, …) so a re-run can never silently overwrite an
    earlier prediction. Returns the id actually written.
    """
    _validate_prediction(record)
    existing = {p.get("id") for p in _read_jsonl(PRED_PATH)[0]}
    rid = record["id"]
    if rid in existing:
        n = 2
        while f"{rid}-{n}" in existing:
            n += 1
        rid = f"{rid}-{n}"
        record = {**record, "id": rid}
    _append_jsonl(PRED_PATH, record)
    return rid


def record_result(pred_id: str, outcome: str | None = None,
                  closing_odds: float | None = None,
                  score: str | None = None) -> None:
    """
    Append an actual result for a logged prediction.
      outcome      : realized 1X2 result ("home"/"draw"/"away") — or "win"/"lose"
                     for a single non-1X2 pick.
      closing_odds : closing price of the HEADLINE pick (for CLV).
      score        : final score "h-a" (e.g. "2-1"); when present, every pick
                     (1X2/O-U/BTTS) is settled exactly, including O/U pushes.
    """
    rec = {"id": pred_id, "outcome": outcome, "closing_odds": closing_odds,
           "score": score}
    _append_jsonl(RES_PATH, rec)


# ── Settling logic ──────────────────────────────────────────────────────────────

def _parse_score(result: dict) -> tuple[int, int] | None:
    s = result.get("score")
    if isinstance(s, str) and "-" in s:
        try:
            h, a = s.split("-")
            return int(h.strip()), int(a.strip())
        except ValueError:
            return None
    return None


def _pick_won(pick: dict, result: dict) -> bool | None:
    """
    Did this pick win? Returns True/False, or None when the result is a PUSH/void
    or cannot be determined (so it is excluded from scoring rather than guessed).
    """
    market = pick.get("market", "")
    sel = pick.get("selection", "")
    goals = _parse_score(result)
    outcome = result.get("outcome")

    if market == "1x2":
        if goals is not None:
            h, a = goals
            res = "home" if h > a else "draw" if h == a else "away"
            return res == sel
        if outcome in ("home", "draw", "away"):
            return outcome == sel
        if outcome in ("win", "lose"):
            return outcome == "win"
        return None

    if market.startswith("ou_"):
        if goals is None:
            return outcome == "win" if outcome in ("win", "lose") else None
        total = goals[0] + goals[1]
        try:
            line = float(market.split("_", 1)[1])
        except (IndexError, ValueError):
            return None
        if total == line:          # whole-number line landed exactly → push/void
            return None
        over = total > line
        return over if sel.startswith("over") else (not over)

    if market == "btts":
        if goals is None:
            return outcome == "win" if outcome in ("win", "lose") else None
        yes = goals[0] >= 1 and goals[1] >= 1
        return yes if sel == "btts_yes" else (not yes)

    # Unknown market: fall back to explicit win/lose, else selection match.
    if outcome in ("win", "lose"):
        return outcome == "win"
    return outcome == sel if outcome is not None else None


# ── Read / calibration path ──────────────────────────────────────────────────

def compute_calibration() -> dict:
    """Join predictions + results and compute the scorecard (every pick scored)."""
    preds_list, bad_pred = _read_jsonl(PRED_PATH)
    results, bad_res = _read_jsonl(RES_PATH)

    preds_by_id: dict[str, list[dict]] = defaultdict(list)
    for p in preds_list:
        if "id" in p:
            preds_by_id[p["id"]].append(p)
    dup_ids = sorted(k for k, v in preds_by_id.items() if len(v) > 1)

    brier_terms: list[float] = []
    clv_terms: list[float] = []
    bucket_hits = {b: [0, 0] for b in BUCKETS}      # band -> [wins, n]
    staked = won = 0
    profit = 0.0
    total_staked = 0.0
    n_res = 0

    for r in results:
        plist = preds_by_id.get(r.get("id"))
        if not plist:
            continue
        n_res += 1
        pred = plist[0]                              # first logged wins the match
        picks = pred.get("picks") or []
        for idx, pick in enumerate(picks):
            win = _pick_won(pick, r)
            if win is None:                          # push / undeterminable → skip
                continue
            my_prob = pick.get("my_prob")
            odds = pick.get("odds")
            stake = pick.get("stake_units", 0.0) or 0.0

            if my_prob is not None:
                brier_terms.append((my_prob - (1.0 if win else 0.0)) ** 2)
                for b in BUCKETS:
                    if b[0] <= my_prob < b[1]:
                        bucket_hits[b][1] += 1
                        if win:
                            bucket_hits[b][0] += 1

            if stake > 0:
                staked += 1
                total_staked += stake
                if win:
                    won += 1
                    profit += stake * (odds - 1.0)
                else:
                    profit -= stake

            # CLV only meaningful for the headline pick's closing price.
            if idx == 0:
                cl = r.get("closing_odds")
                if cl and odds:
                    clv_terms.append(odds / cl - 1.0)

    return {
        "predictions_logged": len(preds_list),
        "unique_prediction_ids": len(preds_by_id),
        "duplicate_ids": dup_ids,
        "results_recorded": n_res,
        "bad_lines": {"predictions": bad_pred, "results": bad_res},
        "brier": round(sum(brier_terms) / len(brier_terms), 4) if brier_terms else None,
        "hit_rate": round(won / staked, 4) if staked else None,
        "roi": round(profit / total_staked, 4) if total_staked else None,
        "profit_units": round(profit, 2),
        "avg_clv": round(sum(clv_terms) / len(clv_terms), 4) if clv_terms else None,
        "n_scored_picks": len(brier_terms),
        "buckets": {
            f"{int(b[0]*100)}-{int(b[1]*100)}%":
                {"hit_rate": round(h[0] / h[1], 3) if h[1] else None, "n": h[1]}
            for b, h in bucket_hits.items()
        },
    }


def pending_predictions() -> list[dict]:
    """Logged predictions that have no result recorded yet (drives the settle loop)."""
    preds, _ = _read_jsonl(PRED_PATH)
    results, _ = _read_jsonl(RES_PATH)
    settled = {r.get("id") for r in results}
    return [{"id": p.get("id"), "match": p.get("match"), "verdict": p.get("verdict")}
            for p in preds if p.get("id") not in settled]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "result" and len(args) >= 3:
        pid, outcome = args[1], args[2]
        closing = None
        score = None
        for extra in args[3:]:
            if "-" in extra and all(part.strip().isdigit() for part in extra.split("-", 1)):
                score = extra                        # looks like a scoreline "h-a"
            else:
                try:
                    closing = float(extra)
                except ValueError:
                    pass
        record_result(pid, outcome, closing, score)
        print(f"Recorded result for {pid}: outcome={outcome} closing={closing} score={score}")
        return

    if args and args[0] == "pending":
        pend = pending_predictions()
        if not pend:
            print("No pending predictions — all logged picks are settled.")
            return
        print(f"{len(pend)} prediction(s) awaiting results:")
        for p in pend:
            print(f"  {p['id']:<24} {p['match']}  [{p['verdict']}]")
        return

    print(json.dumps(compute_calibration(), indent=2))


if __name__ == "__main__":
    main()
