"""Run one blind pass: one Sonnet 5.5 call per packet, with no tools.

    python3 run.py <task> [--only ID ...] [--workers 6] [--effort high]

A task is a folder here holding PROMPT.md and packets/*.md (or, with --prompt, a prompt file elsewhere). Each call
gets the prompt as its instruction and the packet on stdin, with no built-in tools and no MCP servers, from an
empty working directory, as in ../faithfulness-check/run_checks.py. Results go to <task>/results/<id>.json;
existing results are kept, so a rerun only does what is missing. A nonzero CLI exit stops the run.
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
MODEL = "claude-sonnet-5-5"
EMPTY = Path(tempfile.mkdtemp(prefix="trace-analysis-cwd-"))


def parse(text, key):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    data = json.loads(match.group(0))
    if key and key not in data:
        raise ValueError(f"reply lacks {key}")
    return data


def check(job):
    packet_path, prompt, results, effort, key = job
    target = results / f"{packet_path.stem}.json"
    if target.exists():
        return packet_path.stem, "kept"
    command = [WRAPPER, "-p", prompt, "--model", MODEL, "--effort", effort, "--tools", "",
               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"]
    for attempt in (1, 2):
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(command, input=packet_path.read_text(), capture_output=True, text=True, cwd=EMPTY,
                                 timeout=1800)
        if process.returncode != 0:
            raise SystemExit(f"Claude CLI exited {process.returncode}; stopping")
        try:
            envelope = json.loads(process.stdout)
            data = parse(envelope.get("result", ""), key)
        except (ValueError, json.JSONDecodeError) as error:
            if attempt == 2:
                target.with_suffix(".failed.txt").write_text(
                    f"{error}\n\nSTDOUT:\n{process.stdout[-4000:]}\n\nSTDERR:\n{process.stderr[-2000:]}")
                return packet_path.stem, f"failed: {error}"
            continue
        record = {"packet": packet_path.stem, "started": started, "model": MODEL, "effort": effort, "attempt": attempt,
                  "usage": envelope.get("usage"), "duration_ms": envelope.get("duration_ms"), "result": data}
        target.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
        return packet_path.stem, "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--prompt")
    parser.add_argument("--key", help="a top-level key every reply must have")
    parser.add_argument("--execute", action="store_true", help="Allow new, potentially paid model calls")
    args = parser.parse_args()
    if not args.execute:
        parser.error("New evaluations require --execute; copy this archive to a private working directory first")
    task = HERE / args.task
    prompt = Path(args.prompt).read_text() if args.prompt else (task / "PROMPT.md").read_text()
    results = task / "results"
    results.mkdir(exist_ok=True)
    packets = sorted((task / "packets").glob("*.md"))
    if args.only:
        packets = [p for p in packets if p.stem in args.only]
    jobs = [(p, prompt, results, args.effort, args.key) for p in packets]
    with ThreadPoolExecutor(args.workers) as pool:
        for name, status in pool.map(check, jobs):
            print(name, status, flush=True)


if __name__ == "__main__":
    sys.exit(main())
