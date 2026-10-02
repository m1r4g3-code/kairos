"""
KAIROS core — the parts that know nothing about football.

  staking   expected value, fractional Kelly, caps, one-event-one-position
  devig     remove a bookmaker margin (proportional, power, Shin)
  ledger    predictions -> results -> Brier / ROI / CLV; settlement is pluggable
  metrics   log loss, Brier, RPS, calibration buckets, bootstrap intervals
  runlog    append-only log of every variant run

A second agent (for example one working on prediction markets) can import this
package without pulling in any football code. The football engine and the
backtest harness import it through thin shims with the old module names.

Pure stdlib.
"""
