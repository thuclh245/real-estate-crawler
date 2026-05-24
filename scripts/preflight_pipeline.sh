#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$PROJECT_DIR"
export PYTHONPATH=src

if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 --run-id <run_id> [--config <path>] [--require-spark] [--output-dir <dir>]" >&2
  exit 2
fi

if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python -m src.validation.preflight "$@"
fi

exec python -m src.validation.preflight "$@"
