# Making the repository public: what to do first

Written 2026-10-02. Nothing here has been done. Each step is the owner's call.

## What is safe already

- **No secret is in the repository or its history.** `.env` is gitignored and was
  never committed (checked in the Phase 0 audit).
- **The three committed fixtures are made-up data** (`engine/fixtures/*_sample.*`).
  They are not copies of The Odds API, Understat or Football-Data output.
- **No Football-Data file is committed.** `data/` is gitignored; only checksums
  and column names are in `research/data_manifest.json`.
- **Cached Odds API responses are gitignored** (`engine/fixtures/odds_*.json`).
  The Odds API terms forbid redistributing their data, so these must stay out.

## What is personal and is in the history

| File | What it holds |
|---|---|
| `ledger/predictions.jsonl`, `ledger/results.jsonl` | Every pick logged since June 2026, with stakes |
| `ledger/calibration.md` | The running scorecard |
| `CLAUDE.md` | Betting habits, stake size, bookmaker, money-management notes |
| `DEV_AGENT_BRIEF.md` (untracked) | The engagement brief |
| `ledger/pending-slip-2026-09.md` (untracked) | A saved slip |

Deleting these files now would not remove them from earlier commits. If the
repository is switched from private to public, anyone can read the old versions.

## Two ways to go public

**Option A (recommended): publish a clean copy.** Create a new public repository
from the current files without the personal ones and without the old history.
The private repository stays as it is and keeps the full record. Nothing is
rewritten or lost. The cost is that the public copy starts with one commit.

**Option B: rewrite the history of this repository** to remove the personal
files, then make it public. This changes every commit id, needs a forced push,
and cannot be undone on GitHub once pushed. Only worth it if the commit history
itself needs to be public.

## Before either option

1. Decide whether the ledger should be public at all. A public record of picks
   is good for credibility; stakes and bookmaker details may not be wanted.
2. Replace `CLAUDE.md` in the public copy with a version that keeps the
   operating notes and drops the personal ones.
3. Merge the dev branches into `main` first, so the public copy has the audited
   README, the harness and the corrected engine rather than the June state.
4. Keep the README's "Status of the evidence" section. It is what stops a
   reader from taking the project for a proven system.
5. Add a line to the README on where the data comes from and that it is not
   redistributed (already there).
