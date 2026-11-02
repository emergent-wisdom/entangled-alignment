#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--ug-cli" ]; then
    UG_CLI="${2:?Provide a built Understanding Graph bin/cli.js path}"
    shift 2
fi
if [ -n "${UG_CLI:-}" ]; then
    if [ ! -f "$UG_CLI" ]; then
        echo "Error: Understanding Graph CLI not found: $UG_CLI" >&2
        exit 1
    fi
    export PROJECT_DIR="${PROJECT_DIR:-$ROOT/.local-work/projects}"
    export PORT="${PORT:-3000}"
    echo "Starting selected Understanding Graph build: $UG_CLI"
    echo "Projects: $PROJECT_DIR"
    exec node "$UG_CLI" start "$@"
fi

export PROJECT_DIR="${PROJECT_DIR:-$ROOT/projects}"
export PORT="${PORT:-3000}"

echo "Starting Understanding Graph viewer..."
echo "Projects: $PROJECT_DIR"
echo "URL: http://localhost:$PORT"
echo ""

# Use the repo-local, version-pinned install so the viewer matches the server
# the agents write with. Bare `npx understanding-graph` would take whatever is
# newest on npm, so the fallback pins the version too.
LOCAL_BIN="$ROOT/node_modules/.bin/understanding-graph"
if [ -x "$LOCAL_BIN" ]; then
    exec "$LOCAL_BIN" start
else
    echo "Note: no local install found (run ./setup.sh); falling back to npx."
    exec npx -y understanding-graph@0.2.1 start
fi
