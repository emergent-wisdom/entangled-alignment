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

# Load env
if [ -f "$ROOT/.env" ]; then
    export $(grep -v '^#' "$ROOT/.env" | xargs)
else
    echo "Error: No .env found. Copy .env.example to .env and add your API key."
    exit 1
fi

# Set PYTHONPATH for emergent-swarm
export PYTHONPATH="$ROOT/emergent-swarm/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Run the reader
exec python3 "$ROOT/chronological_metacognition/run_reader.py" "$@"
