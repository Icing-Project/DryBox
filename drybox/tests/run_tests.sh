#!/usr/bin/env bash
set -Eeuo pipefail

# Run the DryBox test suite using the project manager "uv".
# - Works on WSL/Linux/macOS
# - Does not assume pytest is preinstalled (ephemeral via --with)
# - Ensures the repo root is on PYTHONPATH so `import drybox` succeeds

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "FATAL: 'uv' not found. Install it from https://docs.astral.sh/uv/ then re-run." >&2
  exit 127
fi

# Make repository root importable for tests (namespace package layout without install step)
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

# Sanity-check inside uv's Python (so the same interpreter/env as pytest will use)
uv run --with pyyaml python - <<'PY'
import sys
try:
    import drybox  # noqa: F401
except Exception as e:
    print("FATAL: cannot import 'drybox' from repo root. Check PYTHONPATH/working dir.", file=sys.stderr)
    raise
PY

# Run pytest inside uv with ephemeral tooling/deps needed by the suite.
# Add cryptography for Ed25519 tests and hypothesis for SAR-lite property tests.
exec uv run \
  --with pytest \
  --with hypothesis \
  --with cryptography \
  --with pyyaml \
  python -m pytest -q drybox/tests
