#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Entangled Alignment Setup ==="
echo ""

# 1. Submodules (orchestrator only). A source snapshot (e.g. the Zenodo
#    archive) ships orchestrator/ vendored and has no .git — skip there.
echo "[1/4] Initializing submodules..."
if [ -e ".git" ]; then
    git submodule update --init --recursive
elif [ -d "orchestrator/src" ]; then
    echo "Not a git checkout; using the bundled orchestrator/."
else
    echo "Error: orchestrator/ is missing and this is not a git checkout."
    exit 1
fi

# 2. Node version gate. The graph store uses better-sqlite3 13 (the 11.x line
#    that shipped with understanding-graph has no prebuilt binaries for current
#    Node and no longer compiles against V8).
echo "[2/4] Checking Node version..."
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" -lt 22 ]; then
    echo "Error: Node 22+ required (found: $(node -v 2>/dev/null || echo 'no node'))."
    exit 1
fi

# 3. Node toolchain — the understanding-graph MCP server and viewer, plus the
#    embedding backend the agents' semantic tools need. Versions are pinned by
#    package.json + package-lock.json and installed locally, not globally, so
#    run.sh and view.sh always get the same build.
echo "[3/4] Installing understanding-graph (pinned)..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

# 4. Python
echo "[4/4] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# 5. Env file
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
echo "  1. ./view.sh                    browse the two included graphs (no API key needed)"
echo "  2. Add your API key to .env     only needed to read a new text"
echo "  3. ./run.sh /path/to/any-book.txt --project my-reading"
