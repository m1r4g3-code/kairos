"""
Staking now lives in core/staking.py (sport-agnostic, reusable by other agents).
This file keeps `import kelly` and existing commands working.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import staking as _impl  # noqa: E402

if __name__ != "__main__":
    sys.modules[__name__] = _impl
