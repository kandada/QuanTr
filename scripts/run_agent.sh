#!/usr/bin/env bash
# Run the optional aacode-based analyst from the repo root.
# Usage: scripts/run_agent.sh [agent args...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 agent/main_quan_tr.py "$@"
