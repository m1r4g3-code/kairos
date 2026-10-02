"""
The ledger now lives in core/ledger.py (sport-agnostic, reusable by other agents).
This file keeps `import ledger` and existing commands working.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ledger as _impl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settle  # noqa: E402

_impl.set_settler(settle.settle_football)      # football rules for this repo's ledger

if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    _impl.main()
