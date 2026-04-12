#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Entangled Alignment Setup ==="
echo ""

# 1. Submodules (orchestrator only)
echo "[1/3] Initializing submodules..."
git submodule update --init --recursive

# 2. Understanding Graph (npm package — pinned to version used in paper)
echo "[2/3] Installing understanding-graph..."
npm install -g understanding-graph@0.1.15

# 3. Python
echo "[3/3] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q google-genai python-dotenv

# 4. Env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example."
    echo "Add your Gemini API key:  $ROOT/.env"
    echo ""
else
    echo ".env already exists, skipping."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Add your API key to .env"
echo "  2. ./run.sh /path/to/any-book.txt --project my-reading"
echo "  3. ./view.sh   (opens http://localhost:3000)"
