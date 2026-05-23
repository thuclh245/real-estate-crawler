#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$PROJECT_DIR"
export PYTHONPATH=src

if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python -m validation.preflight "$@"
fi

exec python -m validation.preflight "$@"
