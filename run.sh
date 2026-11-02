#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Activate venv
if [ -f "$ROOT/.venv/bin/activate" ]; then
    source "$ROOT/.venv/bin/activate"
else
    echo "Error: No .venv found. Run ./setup.sh first."
    exit 1
fi

# run_reader.py loads .env with python-dotenv, including quoted values and
# inline comments. Environment variables supplied by the caller take precedence.

# Set PYTHONPATH for orchestrator
export PYTHONPATH="$ROOT/orchestrator/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Run the reader
exec python3 "$ROOT/chronological_metacognition/run_reader.py" "$@"
