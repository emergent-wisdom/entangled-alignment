"""Run the checks on the packets: Sonnet 5.5 no tools, one call per packet.

    python3 run.py [--only T-01-1 R-01 ...] [--workers 4]

Thought packets (T-*) use ../faithfulness-check/PROMPT.md; record packets (R-*) use RECORD-PROMPT.md.
Results go to results/<packet>.json; existing results are kept. A nonzero CLI exit stops the run. Adapted from ../faithfulness-check/run_checks.py.
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
PROMPTS = {"T": (HERE.parent / "faithfulness-check/PROMPT.md").read_text(), "R": (HERE / "RECORD-PROMPT.md").read_text()}
LISTS = {"T": "misreadings", "R": "problems"}
RESULTS = HERE / "results"
EMPTY = Path(tempfile.mkdtemp(prefix="meaning-model-check-cwd-"))


def parse(text, field):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    data = json.loads(match.group(0))
    if not isinstance(data.get(field), list):
        raise ValueError(f"reply lacks a {field} list")
    return data


def check(packet):
    target = RESULTS / f"{packet}.json"
    if target.exists():
        return packet, "kept"
    kind = packet[0]
    command = [WRAPPER, "-p", PROMPTS[kind], "--model", MODEL, "--effort", EFFORT, "--tools", "",
               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"]
    for attempt in (1, 2):
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(command, input=(HERE / "packets" / f"{packet}.md").read_text(), capture_output=True,
                                 text=True, cwd=EMPTY, timeout=1200)
        if process.returncode != 0:
            raise SystemExit(f"Claude CLI exited {process.returncode}; stopping")
        try:
            envelope = json.loads(process.stdout)
            data = parse(envelope.get("result", ""), LISTS[kind])
        except (ValueError, json.JSONDecodeError) as error:
            if attempt == 2:
                target.with_suffix(".failed.txt").write_text(f"{error}\n\nSTDOUT:\n{process.stdout[-4000:]}\n\nSTDERR:\n{process.stderr[-2000:]}")
                return packet, f"failed: {error}"
            continue
        target.write_text(json.dumps({"packet": packet, "started": started, "model": MODEL, "effort": EFFORT, "attempt": attempt,
                                      "usage": envelope.get("usage"), "duration_ms": envelope.get("duration_ms"), "result": data},
                                     indent=1) + "\n")
        return packet, f"ok ({len(data[LISTS[kind]])} {LISTS[kind]})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--execute", action="store_true", help="Allow new, potentially paid model calls")
    args = parser.parse_args()
    if not args.execute:
        parser.error("New evaluations require --execute; copy this archive to a private working directory first")
    RESULTS.mkdir(exist_ok=True)
    packets = args.only or sorted(path.stem for path in (HERE / "packets").glob("*.md"))
    with ThreadPoolExecutor(args.workers) as pool:
        for packet, status in pool.map(check, packets):
            print(packet, status, flush=True)


if __name__ == "__main__":
    sys.exit(main())
