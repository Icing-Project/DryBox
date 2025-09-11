#!/usr/bin/env bash
set -euo pipefail

# repo root
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Use uv if present; fallback to system Python
run() {
  if command -v uv >/dev/null 2>&1; then
    uv run "$@"
  else
    "$@"
  fi
}

export PYTHONPATH="$ROOT"

# Default: run all tests; allow args passthrough (e.g., -k sar or tests/net)
run pytest -q --maxfail=1 --disable-warnings \
  --cov=drybox/core --cov=drybox/net --cov-report=term-missing \
  ${@:-tests}
