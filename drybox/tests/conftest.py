# Ensure the repository root is importable even if pytest is invoked from a subfolder.
# This keeps `from drybox.core...` imports stable across shells/CI/WSL.
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
p = str(REPO_ROOT)
if p not in sys.path:
    sys.path.insert(0, p)
