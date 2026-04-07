#!/bin/bash
# Use the top-level run.sh instead.
# This script is kept for backward compatibility.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/run.sh" "$@"
