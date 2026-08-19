#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"

export PROJECT_DIR="$ROOT/projects"
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
    exec npx -y understanding-graph@0.1.16 start
fi
