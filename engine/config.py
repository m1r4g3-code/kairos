"""
KAIROS engine — configuration & secrets loader.

Reads key=value pairs from a .env file at the Kairos root (gitignored) into the
process environment, then exposes the settings the data adapters need. Pure
stdlib — no python-dotenv dependency.

Never commit .env. See .env.example for the documented keys.
"""

from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
ENV_PATH = os.path.join(_ROOT, ".env")
CACHE_DIR = os.path.join(_HERE, "fixtures")


def _load_env(path: str = ENV_PATH) -> None:
    """Parse a simple KEY=VALUE .env file into os.environ (existing vars win)."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


_load_env()

# ── Settings ──────────────────────────────────────────────────────────────────
# Accept either THE_ODDS_API_KEY (user's .env naming) or ODDS_API_KEY.
ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = os.environ.get("THE_ODDS_API_BASE_URL", "https://api.the-odds-api.com/v4")

# Optional, for the future environment/weather layer (L9). Not used yet.
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

# Books we trust as "sharp" (closest to true price), in priority order.
SHARP_PRIORITY = ("pinnacle", "betfair_ex_eu", "marathonbet")

# Minimum EV over the sharp fair price before we call something value.
MIN_EDGE = 0.03


def have_key() -> bool:
    """True if an Odds API key is configured (live fetch possible)."""
    return bool(ODDS_API_KEY)
