#!/usr/bin/env python3
"""HAND-WRITTEN, NOT generated.

The conformance gate. A generated client is not done until this exits 0
(CLAUDE.md section 5).

    python scripts/conformance.py <platform>
    python scripts/conformance.py --alice kotlin --bob python
    python scripts/conformance.py --matrix
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
