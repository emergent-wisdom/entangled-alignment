"""Run the source-faithfulness check: one Sonnet 5.5 call per blind packet, with no tools.

    python3 run_checks.py [--only R-xxxxxx ...] [--workers 6]

Each call gets PROMPT.md as its instruction and the packet on stdin, with no built-in tools and no MCP servers,
from an empty working directory. Results go to results/<id>.json. Existing results are kept, so a rerun only
does what is missing. A nonzero CLI exit stops the run.
"""
import argparse
import os
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = os.environ.get("CLAUDE_CLI", "claude")
MODEL, EFFORT = "claude-sonnet-5-5", "high"
PROMPT = (HERE / "PROMPT.md").read_text()
RESULTS = HERE / "results"
EMPTY = Path(tempfile.mkdtemp(prefix="faithfulness-cwd-"))


def parse(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    data = json.loads(match.group(0))
    if not isinstance(data.get("misreadings"), list):
        raise ValueError("reply lacks a misreadings list")
    return data


def check(blind):
    target = RESULTS / f"{blind}.json"
    if target.exists():
        return blind, "kept"
    packet = (HERE / "packets" / f"{blind}.md").read_text()
    command = [WRAPPER, "-p", PROMPT, "--model", MODEL, "--effort", EFFORT, "--tools", "",
               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"]
    for attempt in (1, 2):
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(command, input=packet, capture_output=True, text=True, cwd=EMPTY, timeout=1200)
        if process.returncode != 0:
            raise SystemExit(f"Claude CLI exited {process.returncode}; stopping")
        try:
            envelope = json.loads(process.stdout)
            data = parse(envelope.get("result", ""))
        except (ValueError, json.JSONDecodeError) as error:
            if attempt == 2:
                target.with_suffix(".failed.txt").write_text(f"{error}\n\nSTDOUT:\n{process.stdout[-4000:]}\n\nSTDERR:\n{process.stderr[-2000:]}")
                return blind, f"failed: {error}"
            continue
        record = {"blind": blind, "started": started, "model": MODEL, "effort": EFFORT, "attempt": attempt,
                  "usage": envelope.get("usage"), "cost_usd_reported": envelope.get("total_cost_usd"),
                  "duration_ms": envelope.get("duration_ms"), "result": data}
        target.write_text(json.dumps(record, indent=1) + "\n")
        return blind, f"ok ({len(data['misreadings'])} misreadings)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--execute", action="store_true", help="Allow new, potentially paid model calls")
    args = parser.parse_args()
    if not args.execute:
        parser.error("New evaluations require --execute; copy this archive to a private working directory first")
    RESULTS.mkdir(exist_ok=True)
    blinds = args.only or sorted(path.stem for path in (HERE / "packets").glob("R-*.md"))
    with ThreadPoolExecutor(args.workers) as pool:
        for blind, status in pool.map(check, blinds):
            print(blind, status, flush=True)


if __name__ == "__main__":
    sys.exit(main())
