#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"

export PROJECT_DIR="$ROOT/projects"
export PORT="${PORT:-3000}"

echo "Starting Understanding Graph viewer..."
echo "Projects: $PROJECT_DIR"
echo "URL: http://localhost:$PORT"
echo ""

exec npx -y understanding-graph start
