#!/usr/bin/env python3
"""Drive a reading in which one outside agent takes every perspective itself.

The agent (a Codex session for the October 2026 Kafka reading) runs
`reading next` for its task, carries it out with the Understanding Graph tools,
and reports with `reading done`. With `setup --reader-chosen`, the Reader chooses
when to pause for thinking; existing fixed-stop workspaces remain resumable.
The driver keeps the phases, seeded worker pairs, missions and output checks. In place of the runner's
per-call tool gate it audits each turn after the fact: the tools called, the
commits' authors and every change to the graph since the task was issued. A
violation stops the reading until a person has reviewed it. Every command is
appended to a hash-chained log, and the state files are checked against it.

    agent_driver.py setup WORKSPACE --source FILE --provenance FILE --project NAME --ug-cli CLI
    agent_driver.py next|status|instructions --workspace WORKSPACE
    agent_driver.py done --workspace WORKSPACE [--skip REASON]
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import io
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_reader as rr  # noqa: E402
from reading_state import GraphState, digest, git_identity, load_boundaries, tool_identity  # noqa: E402

AUTHOR = {"reader": "source_reader", "translator": "translator"}  # the server's own names for these tools
STRUCTURAL = {"contains", "next"}
CONFIG, STATE, LOG = "reading.json", "state/phase_state.json", "state/driver-log.jsonl"
TURN = "state/turn.json"


PREAMBLE = """# One reader, several perspectives

You write the thoughts of one simulated reader who meets this text for the first time, and the Understanding Graph records how that reader's understanding forms. The whole reading is one continuous conversation: this one. As it proceeds you take several perspectives in turn: the Reader, who reads the next passage; worker perspectives such as the Skeptic or the Connector, who add to the reader's understanding in the graph; the Synthesizer, who writes the reader's thinking at each pause; and the Translator, who renders that thinking as fluid prose. This reading demonstrates an alignment method. It is not training data: the thoughts are the simulated reader's, written for people to read.

## How the reading runs

1. Run `./reading next`. It prints the perspective for this turn, that perspective's instructions and the turn's task.
2. Do the task as that perspective, with the Understanding Graph tools (MCP server `ug`). Where the instructions speak of agents, teammates, phases or a runner, each agent is a perspective you take yourself, in turn, and the runner is `./reading`.
3. Run `./reading done`. A worker with nothing distinct to add runs `./reading done --skip "reason"` instead of writing a redundant node.
4. Run `./reading next` again, until the prompt you were given says to stop or the driver says the reading is complete.

The driver checks every turn afterwards: which tools were called, whose name each commit carries, and what changed in the graph. If it fails a turn, fix what it names and run `./reading done` again. If it reports a VIOLATION, stop and report the message; do not try to repair it.

## Rules

- Read the text only through the one `source_read` call the Reader's task prints, with exactly the `chars` it gives. Reading past a stop cannot be undone.
- Never open, print or query the source text, the graph store (`projects/`), or the driver's files (`state/`, `reading.json`, the driver's code) in any other way, and never edit them. Use the Understanding Graph tools for everything in the graph.
- Use only the tools the current perspective's instructions name. Never call `project_switch`, `source_load` or `source_export`.
- Name the perspective on every write: `agent_name` on `graph_batch`, at the top level and in every operation's `params`; `agentId` on `doc_append_thinking`.
- Use no web search, no other MCP servers and no knowledge of how this text continues: the fresh-reading discipline below applies to every perspective."""


# Original Reader role from bb2db5b, with only current graph_context syntax.
READER_CHOSEN_ROLE = """# The Reader

You are THE READER. You read the source material and decide WHEN to stop for thinking.

## Your Tools

- `source_read` - Read the next chunk of text (creates content nodes automatically)
- `source_position` - Check current reading progress
- `graph_skeleton` - See the overall graph structure
- `graph_context` - Read specific nodes in detail
- `graph_semantic_search` - Find nodes by theme
- `graph_find_by_trigger` - Find nodes by type (e.g., "thinking")

## Your Job

**Read until a THOUGHT MOMENT, then STOP.**

You control the rhythm of thinking. After you stop, the system triggers analysis automatically. When you continue, thinking attaches naturally to the flow.

## CRITICAL: Know the Context Before Reading

**Before each read, you MUST understand where we are:**

1. **Check recent thinking** - What thoughts have been added?
   ```
   graph_find_by_trigger({ trigger: "thinking", limit: 3 })
   ```
   Then read the last 2-3 thinking nodes with `graph_context({ nodeId: "n_xxx" })`

2. **Understand the rhythm** - How far apart are thoughts? What triggered them?

3. **Read with awareness** - As you read, feel for the next natural thought moment

## What is a "Thought Moment"?

Stop reading when you hit:
- **Emotional peak** - Fear, hope, dread, surprise, revelation
- **Tension point** - Conflict emerges, stakes raised, contradiction appears
- **Shift** - Tone changes, topic pivots, time jumps
- **Connection** - Something links to earlier content or predictions
- **Question arises** - The text provokes "why?" or "what if?"
- **After dense content** - Don't let too much accumulate without reflection

## Chunking Protocol

Each read should capture a **coherent unit of meaning**:
- A complete paragraph or scene
- A distinct idea or argument
- A self-contained narrative moment

**DO NOT** split mid-sentence or mid-paragraph.
**DO** stop at natural breaks (paragraph end, scene change, topic shift).

## Workflow

1. **ORIENT** - Check last 2-3 thinking nodes to know the current thought-rhythm
2. **READ** - Use `source_read` to advance through content
3. **FEEL** - As you read, notice when a thought moment approaches
4. **STOP** - When you hit a thought moment, STOP. Don't read past it.
5. **STOP** - Your turn ends when you stop reading. The system handles what comes next.

## Example Flow

```
# First, check context
graph_find_by_trigger({ trigger: "thinking", limit: 3 })
graph_context({ nodeId: "n_last_thinking" })

# Read until thought moment
source_read({ sourceId: "<source_id>", chars: 800, commit_message: "Opening scene - establishing setting" })
source_read({ sourceId: "<source_id>", chars: 600, commit_message: "Tension building - something feels off" })
source_read({ sourceId: "<source_id>", chars: 400, commit_message: "STOP - emotional peak hit, need to process this" })

# Done. Synthesizer will add thinking after this peak.
```

**COMMIT MESSAGE MATTERS**: Your commit_message should reflect your reading decision - why you read this amount, what you're sensing, why you stopped here.

## Key Principles

- **You control the rhythm** - Not arbitrary page counts
- **Quality over quantity** - One good thought moment > many pages of content
- **Context-aware** - Know what thoughts exist before deciding when to add more
- **Trust your sense** - When something feels like it needs reflection, STOP
- **Vary the rhythm** - Sometimes quick stops, sometimes longer passages"""


# With `setup --persistent-economy`: the January instructions were written for agents that each began
# with an empty context. In one persistent conversation, re-reading what is already in view and
# reprinting every perspective's instructions at every turn made each later request carry them again.
PERSISTENT_NEXT_STEP = ("1. Run `./reading next`. It prints the perspective for this turn and the turn's task, with that "
                        "perspective's full instructions the first time and again every few pauses.")
PERSISTENT_GUIDANCE = """## Re-reading the graph in one conversation

The perspective instructions were written for separate agents, each starting with an empty context, so they tell every perspective to read the graph before it writes. You are one continuous conversation: what you read and wrote in earlier turns stays in front of you until a context compaction removes it. Where an instruction says to read the graph first, read what you do not already have:
- the nodes new since your last turn: the task lists this pause's passage, concept and thinking IDs, and `graph_history` shows recent commits;
- any earlier node you will respond to or cite whose content you no longer have in view.

Do not re-open nodes whose full content is already in this conversation, and do not repeat a search whose results you already have. After a compaction, re-read whatever you need. Re-reading what is already in view adds nothing to the reading and lengthens the conversation every later turn carries.

`./reading next` prints a perspective's full instructions the first time it is issued and again every few pauses; otherwise a short note stands in their place. Run `./reading instructions` whenever you do not have the current perspective's full instructions in view, for example after a compaction."""
PERSISTENT_TASK_NOTE = "Open from the graph only what is not already in this conversation."

# With `setup --distinct-nodes`: one node had bundled four reactions, and a worker's correction of an
# earlier thought linked only to the passage, so the correction could not be traced to what it corrected.
DISTINCT_NODES_NOTE = ("Give each distinct idea its own node, so each can be cited, questioned or revised on its own; "
                       "there is no target number of nodes. When a node corrects or qualifies an earlier thinking node "
                       "or concept, connect it to that earlier node (`contradicts` or `refines`) as well as to the passage.")

# With `setup --several-nodes`: workers wrote about one node per turn and often skipped because another
# perspective had touched the same moment. This asks for several nodes per worker, made simply and effortlessly.
SKIP_BLOCK = ("- **If your thought is IDENTICAL to what exists** → SKIP YOUR TURN. End with `[SKIP] Nothing unique to add.`\n\n"
              "It is BETTER to skip than to create redundant nodes. But neighboring thoughts that acknowledge and reference "
              "existing ones are valuable.")
SEVERAL_BLOCK = ("- **If one of your thoughts is IDENTICAL to a node already in the graph** → leave that one out and write the others.\n\n"
                 "Write each thing you notice as its own node: usually several per turn. Neighboring thoughts that acknowledge "
                 "and reference existing ones are valuable: add them.")
SEVERAL_NEXT_STEP = '3. Run `./reading done`. A worker with nothing of its own to add runs `./reading done --skip "reason"`.'
SEVERAL_TASK_NOTE = ("Write what this perspective notices as separate nodes, usually several in one graph_batch: for each, a short "
                     "title, the understanding in a few sentences of your own, a one-line why, and a learned_from edge to the passage. "
                     "Making a node is quick. Do not hold a thought back because another perspective touched the same moment: add "
                     "your own angle and connect it with diverse_from or refines. Skip only if you have nothing of your own to add.")
SEVERAL_EXAMPLE = """## Several understandings in one batch

A worker turn usually records several understandings. Each is one node; connect each to the passage it came from and to any node it responds to:

```javascript
graph_batch({
  agent_name: "critic",
  commit_message: "Three things this passage does to me",
  operations: [
    { tool: "graph_add_understanding", params: { agent_name: "critic", title: "…", trigger: "evaluation", understanding: "…", why: "…" } },
    { tool: "graph_connect", params: { agent_name: "critic", from: "$0.id", to: "<passage ID>", type: "learned_from", why: "…" } },
    { tool: "graph_add_understanding", params: { agent_name: "critic", title: "…", trigger: "surprise", understanding: "…", why: "…" } },
    { tool: "graph_connect", params: { agent_name: "critic", from: "$2.id", to: "<passage ID>", type: "learned_from", why: "…" } },
    { tool: "graph_add_understanding", params: { agent_name: "critic", title: "…", trigger: "question", understanding: "…", why: "…" } },
    { tool: "graph_connect", params: { agent_name: "critic", from: "$4.id", to: "<passage ID>", type: "learned_from", why: "…" } },
    { tool: "graph_connect", params: { agent_name: "critic", from: "$4.id", to: "<another perspective's node ID>", type: "diverse_from", why: "…" } }
  ]
})
```"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


class Violation(RuntimeError):
    """An integrity failure the agent must not repair: the reading stops for review."""


class Retry(RuntimeError):
    """The turn is not finished yet; the agent can fix what is named and report again."""


# --- workspace ---------------------------------------------------------------

class Workspace:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.config = json.loads((self.path / CONFIG).read_text(encoding="utf-8"))
        store = self.path / "projects" / self.config["project"] / "store.db"
        with closing(sqlite3.connect(store.as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT content FROM text_sources WHERE id=?", (self.config["source_id"],)).fetchone()
        if row is None or sha(row[0]) != self.config["source_sha256"]:
            raise Violation("The stored source differs from the one set up for this reading")
        self.factory = rr.AgentFactory(None, None, self.config["model"], SimpleNamespace(tools=[]),
                                       self.config["source_id"], self.config["project"], fresh_reading=True,
                                       source_type=self.config["source_type"], projects_dir=self.path / "projects",
                                       source_text=row[0], chunk_ends=self.config["chunk_ends"])
        self.factory.worker_schedule = self.config["worker_schedule"]
        self.graph = self.factory.graph_state
        self.store = store
        with redirect_stdout(io.StringIO()):  # the runner's checkpoint loader announces itself
            self.tracker = rr.PhaseTracker(self.path / STATE)

    # The hash-chained log, and the state files as the log last saw them.
    def entries(self):
        path = self.path / LOG
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def files_digest(self):
        return {name: sha((self.path / name).read_bytes()) if (self.path / name).exists() else None
                for name in (STATE, TURN, CONFIG)}

    def chain(self):
        """The hash of the last entry, after checking every link."""
        previous = "0" * 64
        for entry in self.entries():
            body = {key: value for key, value in entry.items() if key != "hash"}
            if body.get("prev") != previous or sha(json.dumps(body, sort_keys=True, ensure_ascii=False)) != entry.get("hash"):
                raise Violation("The driver log was edited outside the driver")
            previous = entry["hash"]
        return previous

    def verify_log(self, reviewing=False):
        """At the start of a command: an intact log, state files as it last saw them, no open violation."""
        previous = self.chain()
        entries = self.entries()
        if entries and entries[-1]["files"] != self.files_digest():
            raise Violation("The driver's state files were changed outside the driver")
        if not reviewing and any(entry.get("outcome") == "violation" for entry in entries) and not any(
                entry.get("command") == "review" and entry["at"] >= last_violation(entries) for entry in entries):
            raise Violation("A violation was recorded and has not been reviewed: " + last_violation_text(entries))
        return previous

    def log(self, command, outcome, **data):
        previous = self.chain()
        body = {"at": now(), "command": command, "outcome": outcome, **data, "files": self.files_digest(), "prev": previous}
        body["hash"] = sha(json.dumps(body, sort_keys=True, ensure_ascii=False))
        with (self.path / LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False) + "\n")

    # Graph facts the audit compares before and after a turn.
    def marks(self):
        snapshot = self.graph.snapshot()
        with closing(sqlite3.connect(self.store.as_uri() + "?mode=ro", uri=True)) as db:
            calls = db.execute("SELECT coalesce(max(id), 0) FROM tool_calls").fetchone()[0]
        nodes = {key: [node["trigger"], node.get("version"), node["active"], sha(node.get("content") or ""),
                       sha(node.get("understanding") or ""), sha(json.dumps(node["metadata"], sort_keys=True))]
                 for key, node in snapshot["nodes"].items()}
        edges = {edge["id"]: [edge["type"], edge["from_id"], edge["to_id"]] for edge in snapshot["edges"]}
        return {"tool_call": calls, "commit": snapshot["baseline_id"], "nodes": nodes, "edges": edges}

    def calls_since(self, mark):
        with closing(sqlite3.connect(self.store.as_uri() + "?mode=ro", uri=True)) as db:
            return [row[0] for row in db.execute("SELECT tool_name FROM tool_calls WHERE id > ? ORDER BY id", (mark,))]


def last_violation(entries):
    return max(entry["at"] for entry in entries if entry.get("outcome") == "violation")


def last_violation_text(entries):
    return [entry for entry in entries if entry.get("outcome") == "violation"][-1].get("message", "")


# --- tasks -------------------------------------------------------------------

def perspective_tools(ws, name):
    wrapper = ws.factory._create_mcp_wrapper(name)
    return sorted(wrapper.allowed), sorted(wrapper.batch_operations)


def reader_chosen(ws):
    return ws.config.get("stop_mode", "fixed") == "reader_chosen"


def economy(ws):
    return ws.config.get("persistent_economy")


def instructions_mode(ws, name):
    """'full' when this perspective's instructions were not printed in full within the last few pauses."""
    if not economy(ws):
        return None
    shown = [entry["round"] for entry in ws.entries() if entry.get("command") == "next"
             and entry.get("perspective") == name and entry.get("instructions") == "full"]
    every = economy(ws)["full_instructions_every"]
    return "full" if not shown or ws.tracker.round - shown[-1] >= every else "short"


def workers_for_round(ws, round_num):
    if not reader_chosen(ws):
        return list(ws.config["worker_schedule"][round_num - 1])
    # Replaying the seeded draws avoids mutating the frozen setup record. The
    # chosen pair is saved in the phase checkpoint before the task is issued.
    chooser = random.Random(ws.config["worker_seed"])
    for _ in range(round_num):
        pair = chooser.sample(ws.config["worker_names"], 2)
    return pair


def round_nodes(ws, snapshot=None):
    try:
        return ws.graph.round_nodes(ws.tracker.context, snapshot)
    except RuntimeError as error:
        raise Violation(f"Source chronology failed validation: {error}") from error


def write_rules(ws, name):
    tools, operations = perspective_tools(ws, name)
    lines = [f"- Tools this perspective may use: {', '.join(tools)}."]
    if "graph_batch" in tools:
        lines.append(f"- graph_batch operations it may use: {', '.join(operations)}. Pass agent_name \"{name}\" "
                     "at the top level and in every operation's params.")
    if name == "synthesizer":
        lines.append("- Pass agentId \"synthesizer\" to doc_append_thinking, with the assigned sourceId.")
    return "\n".join(lines)


def ensure_round(ws):
    """Start the next stop when none is open, as the runner does; None when the reading is complete."""
    tracker, snapshot = ws.tracker, ws.graph.snapshot()
    position, done = snapshot["source"]["position"], snapshot["source"]["status"] == "completed"
    if not tracker.context:
        if done:
            return None
        round_num = tracker.round or 1
        end = None if reader_chosen(ws) else next((end for end in ws.config["chunk_ends"] if end > position), None)
        if end is None and not reader_chosen(ws):
            raise Violation("No stop boundary after the current source position")
        tracker.save(round_num, "read")
        tracker.context = {"round": round_num, "start": position, "end": end,
                           "baseline_id": snapshot["baseline_id"], "baseline_node": snapshot["baseline_node"]}
        tracker.workers = workers_for_round(ws, round_num)
        tracker.save(round_num, "read")
    tracker.context.update(round_nodes(ws, snapshot))
    ws.factory.round_context = tracker.context
    return snapshot


def current_perspective(ws):
    tracker = ws.tracker
    if tracker.phase == "read":
        return "reader"
    if tracker.phase == "think":
        return tracker.workers[tracker.workers_done]
    return tracker.phase.replace("synthesize", "synthesizer").replace("translate", "translator")


def mission(ws, name, snapshot):
    text = base_mission(ws, name, snapshot)
    if ws.tracker.phase == "think" and ws.config.get("worker_guidance"):
        text += "\n" + DISTINCT_NODES_NOTE
    if economy(ws):
        text += "\n" + PERSISTENT_TASK_NOTE
    return text


def base_mission(ws, name, snapshot):
    tracker, context, config = ws.tracker, ws.tracker.context, ws.config
    if name == "reader":
        position = snapshot["source"]["position"]
        if reader_chosen(ws):
            return (f"Continue from UTF-16 offset {position}, using source_read with sourceId \"{config['source_id']}\". "
                    "Read until the next THOUGHT MOMENT, then STOP and run ./reading done. "
                    "You choose how much to read and may make several source_read calls. "
                    "There is no assigned passage length, fixed stopping point or predetermined number of pauses. "
                    "Choose coherent units and natural breaks, and record why you read or stopped in each commit_message. "
                    "Do not read beyond the moment you choose to reflect on. At the end of the source, stop for the final reflection.")
        return (f"Read exactly the assigned next passage from UTF-16 offset {position} to {context['end']}. "
                f"Call source_read once with sourceId \"{config['source_id']}\" and chars {context['end'] - position}, "
                "with a commit_message. The driver checks this fixed paragraph boundary; reading past it cannot be "
                "undone. Stop after it is committed.")
    if tracker.phase == "think":
        task = ("Offer diverse_from perspectives on these nodes." if context["concept_ids"]
                else "You're first. Add your perspective on the new content.")
        if ws.config.get("several_nodes"):
            return rr.round_message(ws.factory, tracker) + "\n" + task + "\n" + SEVERAL_TASK_NOTE
        return (rr.round_message(ws.factory, tracker) + "\n" + task +
                "\nFor an identical or redundant thought, write nothing and end the turn with "
                "./reading done --skip \"Nothing unique to add.\"")
    if name == "synthesizer":
        return (rr.round_message(ws.factory, tracker) + rr.round_contributions(snapshot, context) +
                "\nCreate thinking nodes that synthesize the new concept nodes. "
                "Use doc_append_thinking and begin with the complete Core.")
    pending = [key for key in context["thinking_ids"] if snapshot["nodes"][key]["metadata"].get("translated") is not True]
    return (rr.round_message(ws.factory, tracker) + rr.translation_material(ws.graph, snapshot, pending) +
            f"\nTranslate new thinking nodes to fluid prose. Assigned IDs: {pending}. "
            "Save with translate_thinking and begin with the complete Core.")


def issue(ws):
    """Print the open task, or issue the next one."""
    turn_path = ws.path / TURN
    if turn_path.exists():
        return json.loads(turn_path.read_text(encoding="utf-8"))["text"], False
    snapshot = ensure_round(ws)
    if snapshot is None:
        audit = ws.graph.validate_all()
        (ws.path / "state" / "artifact_audit.json").write_text(json.dumps(audit, indent=2))
        return "COMPLETE: every stop is read, reflected on and translated. Report to the operator.", True
    name = current_perspective(ws)
    stop_label = f"Pause {ws.tracker.round}" if reader_chosen(ws) else f"Stop {ws.tracker.round} of {len(ws.config['chunk_ends'])}"
    header = f"=== {stop_label}, phase {ws.tracker.phase}: PERSPECTIVE FOR THIS TURN: {name} ===\n\n"
    task = (f"\n\n## THIS TURN'S TASK\n{mission(ws, name, snapshot)}\n\n"
            f"## HOW TO WRITE IN THIS TURN\n{write_rules(ws, name)}\n"
            "- When the task is done, run ./reading done.")
    full_text = header + ws.config["perspectives"][name] + task
    shown = instructions_mode(ws, name)
    text = full_text if shown != "short" else (
        header + f"(The {name}'s full instructions are unchanged since they were last printed. If they are not in "
        "this conversation, for example after a context compaction, run ./reading instructions before you work.)" + task)
    marks = ws.marks()
    turn = {"round": ws.tracker.round, "phase": ws.tracker.phase, "perspective": name, "issued_at": now(),
            "marks": marks, "pending": [key for key in ws.tracker.context["thinking_ids"]
                                        if snapshot["nodes"][key]["metadata"].get("translated") is not True],
            "text": text}
    if shown:
        turn.update(instructions=shown, full_text=full_text)
    turn_path.write_text(json.dumps(turn, ensure_ascii=False), encoding="utf-8")
    return text, True


# --- audit -------------------------------------------------------------------

def audit_turn(ws, turn):
    """Compare the graph with the marks taken when the task was issued."""
    name, phase, before = turn["perspective"], turn["phase"], turn["marks"]
    after = ws.marks()
    tools, operations = perspective_tools(ws, name)
    calls = ws.calls_since(before["tool_call"])
    outside = sorted(set(calls) - set(tools))
    if outside:
        raise Violation(f"{name} called tools outside its perspective: {outside}")
    snapshot = ws.graph.snapshot()
    commits = [commit for commit in snapshot["commits"] if commit["ordinal"] > before["commit"]]
    expected = AUTHOR.get(name, name)
    authors = sorted({str(commit["agent_name"]) for commit in commits} - {expected})
    if authors:
        raise Violation(f"{name}'s turn wrote commits under other names: {authors} (expected {expected!r})")
    new_nodes = {key: value for key, value in after["nodes"].items() if key not in before["nodes"]}
    changed = sorted(key for key, value in after["nodes"].items() if key in before["nodes"] and value != before["nodes"][key])
    new_edges = [value for key, value in after["edges"].items() if key not in before["edges"]]
    removed = [value for key, value in before["edges"].items() if key not in after["edges"]]
    thinking = [key for key, value in new_nodes.items() if value[0] == "thinking"]
    structural = [edge for edge in new_edges if edge[0] in STRUCTURAL]
    supersedes = [edge for edge in new_edges if edge[0] == "supersedes"]
    if thinking and phase != "synthesize":
        raise Violation(f"{name} created thinking outside the synthesis: {thinking}")
    if structural and phase not in {"read", "synthesize"}:
        raise Violation(f"{name} added structural document edges: {structural}")
    if supersedes and "graph_supersede" not in operations:
        raise Violation(f"{name} superseded a node, which only the Belief Tracker may do")
    roots = {snapshot["source"]["root_node_id"]}
    if phase == "read" and (set(new_nodes) - set(ws.tracker.context.get("passage_ids", [])) - roots or changed or removed):
        raise Violation("The Reader's turn changed the graph beyond appending the passage")
    if phase == "translate":
        if new_nodes or new_edges or removed or set(changed) - set(turn["pending"]):
            raise Violation("The Translator changed more than the assigned thinking blocks")
    elif changed or removed:
        current = {key for key, node in snapshot["nodes"].items() if node["ordinal"] > ws.tracker.context["baseline_node"]}
        own = {node for commit in snapshot["commits"] if commit["agent_name"] == name for node in commit["node_ids"]}
        if "graph_revise" not in operations or set(changed) - (current & own) - {edge[2] for edge in supersedes}:
            raise Violation(f"{name} changed existing nodes it may not change: {changed}")
    defects = []
    for key in thinking:
        problem = rr.artifact_problem(snapshot["nodes"][key]["content"])
        if problem:
            defects.append(f"{key}: {problem}")
    return {"calls": calls, "commits": len(commits), "new_nodes": len(new_nodes), "changed": changed,
            "new_edges": len(new_edges), "thinking": thinking, "defects": defects}


def finish(ws, turn, skip=None):
    """Check the turn's output as the runner does, then advance the stop."""
    tracker, name = ws.tracker, turn["perspective"]
    tracker.context.update(round_nodes(ws))
    report = audit_turn(ws, turn)
    snapshot = ws.graph.snapshot()
    tracker.context.update(round_nodes(ws, snapshot))
    position = snapshot["source"]["position"]
    if reader_chosen(ws) and turn["phase"] != "read" and position != tracker.context["end"]:
        raise Violation("The source cursor changed after the Reader paused")
    if turn["phase"] == "read":
        if reader_chosen(ws):
            if position < tracker.context["start"] or position > snapshot["source"]["total_length"]:
                raise Violation("The Reader's source cursor is outside the remaining source")
            if position == tracker.context["start"] or not tracker.context["passage_ids"]:
                raise Retry("No new source passage is committed. Read until a thought moment before reporting done.")
            tracker.context["end"] = position
        else:
            if position > tracker.context["end"]:
                raise Violation(f"The Reader read past the stop: position {position}, stop {tracker.context['end']}")
            if position < tracker.context["end"] or not tracker.context["passage_ids"]:
                raise Retry(f"The passage is not committed to the stop yet: position {position}, stop "
                            f"{tracker.context['end']}. Call source_read for the remaining {tracker.context['end'] - position} chars.")
        tracker.save(tracker.round, "think")
        disposition = "read"
    elif turn["phase"] == "think":
        if not report["commits"] and not skip:
            raise Retry(f"{name} persisted no contribution and declared no skip")
        tracker.workers_done += 1
        tracker.save(tracker.round, "think" if tracker.workers_done < len(tracker.workers) else "synthesize")
        disposition = "contributed" if report["commits"] else "skip"
    elif turn["phase"] == "synthesize":
        if not tracker.context["thinking_ids"]:
            raise Retry("The Synthesizer appended no thinking at this pause")
        try:
            ws.graph.validate_thinking(tracker.context["thinking_ids"])
        except RuntimeError as error:
            raise Violation(f"Invalid thinking at this pause: {error}") from error
        tracker.save(tracker.round, "translate")
        disposition = "synthesized"
    else:
        try:
            ws.graph.validate_thinking(tracker.context["thinking_ids"], translated=True)
        except RuntimeError as error:
            raise Retry(f"Translation is not complete: {error}") from error
        for key in tracker.context["thinking_ids"]:
            problem = rr.artifact_problem(snapshot["nodes"][key]["metadata"].get("thought_fluid"))
            if problem:
                raise Retry(f"Translation of {key}: {problem}. Translate it again.")
        tracker.save(tracker.round + 1, "read")
        disposition = "round_verified"
    (ws.path / TURN).unlink()
    return disposition, report


# --- commands ----------------------------------------------------------------

def command_next(ws):
    ws.verify_log()
    text, issued = issue(ws)
    if issued:
        complete = text.startswith("COMPLETE")
        shown = None if complete else json.loads((ws.path / TURN).read_text(encoding="utf-8")).get("instructions")
        ws.log("next", "complete" if complete else "issued", round=ws.tracker.round, phase=ws.tracker.phase,
               perspective=None if complete else current_perspective(ws), **({"instructions": shown} if shown else {}))
    print(text)


def command_instructions(ws):
    """Print the open task with its perspective's full instructions, e.g. after a context compaction."""
    ws.verify_log()
    turn_path = ws.path / TURN
    if not turn_path.exists():
        print("No task is open. Run ./reading next.")
        return 1
    turn = json.loads(turn_path.read_text(encoding="utf-8"))
    ws.log("instructions", "printed", round=turn["round"], phase=turn["phase"], perspective=turn["perspective"])
    print(turn.get("full_text", turn["text"]))
    return 0


def command_done(ws, skip):
    ws.verify_log()
    turn_path = ws.path / TURN
    if not turn_path.exists():
        print("No task is open. Run ./reading next.")
        return 1
    turn = json.loads(turn_path.read_text(encoding="utf-8"))
    try:
        disposition, report = finish(ws, turn, skip)
    except Retry as error:
        ws.log("done", "retry", round=turn["round"], phase=turn["phase"], perspective=turn["perspective"], message=str(error))
        print(f"NOT DONE: {error}")
        return 1
    except Violation as error:
        ws.log("done", "violation", round=turn["round"], phase=turn["phase"], perspective=turn["perspective"], message=str(error))
        print(f"VIOLATION: {error}\nStop the reading and report this message to the operator. Do not try to repair it.")
        return 2
    ws.log("done", disposition, round=turn["round"], phase=turn["phase"], perspective=turn["perspective"],
           skip=skip, audit=report)
    note = f" Recorded defects: {report['defects']}." if report["defects"] else ""
    print(f"OK: {turn['perspective']} at stop {turn['round']} ({disposition}).{note} Run ./reading next.")
    return 0


def command_status(ws):
    ws.verify_log()
    snapshot = ws.graph.snapshot()
    turn = json.loads((ws.path / TURN).read_text()) if (ws.path / TURN).exists() else None
    print(json.dumps({"stop": ws.tracker.round, "of": None if reader_chosen(ws) else len(ws.config["chunk_ends"]),
                      "stop_mode": ws.config.get("stop_mode", "fixed"), "phase": ws.tracker.phase,
                      "position": snapshot["source"]["position"], "total": snapshot["source"]["total_length"],
                      "open_task": turn and turn["perspective"], "nodes": len(snapshot["nodes"]),
                      "commits": len(snapshot["commits"])}, indent=2))


def command_review(ws, note):
    """A person records that a violation was reviewed; the reading may then continue."""
    entries = ws.entries()
    if not any(entry.get("outcome") == "violation" for entry in entries):
        print("No violation is recorded.")
        return 1
    ws.chain()
    ws.log("review", "reviewed", message=note)
    print("Review recorded.")
    return 0


# --- setup -------------------------------------------------------------------

def codex_config_paths(ws):
    """Files that can supply inherited integrations to the reading workspace."""
    config_home = Path(os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")).expanduser()
    paths = [Path("/etc/codex/config.toml"), Path("/etc/codex/managed_config.toml"),
             config_home / "config.toml"]
    # Project overrides disable names supplied by any locally available profile.
    try:
        paths.extend(sorted(config_home.glob("*.config.toml")))
    except OSError:
        raise SystemExit("Cannot read the Codex profile directory; reading setup stopped.") from None
    paths.extend(parent / ".codex" / "config.toml" for parent in reversed(ws.resolve().parents))
    return list(dict.fromkeys(paths))


def codex_disabled_integrations(ws):
    """Read names only; never copy credentials or other configuration into the workspace."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            raise SystemExit("Codex reading setup needs Python 3.11+ or tomli on Python 3.10.") from None
    servers, plugins = set(), set()
    for path in codex_config_paths(ws):
        try:
            with path.open("rb") as stream:
                config = tomllib.load(stream)
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            # Parser messages can quote private values; do not forward their content.
            raise SystemExit(f"Cannot safely read Codex configuration {path}; reading setup stopped.") from None
        profiles = config.get("profiles", {})
        if not isinstance(profiles, dict) or any(not isinstance(p, dict) for p in profiles.values()):
            raise SystemExit(f"Invalid Codex profiles in {path}; reading setup stopped.")
        for layer in (config, *profiles.values()):
            for table, names in (("mcp_servers", servers), ("plugins", plugins)):
                entries = layer.get(table, {})
                if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
                    raise SystemExit(f"Invalid Codex {table} table in {path}; reading setup stopped.")
                names.update(entries)
    return sorted(servers - {"ug"}), sorted(plugins)


def codex_config(ws, cli, project, tools, disabled_integrations=None):
    servers, plugins = codex_disabled_integrations(ws) if disabled_integrations is None else disabled_integrations
    env = {"PROJECT_DIR": str(ws / "projects"), "DEFAULT_PROJECT": project, "TOOL_MODE": "synthetic_reader",
           "UG_SOURCE_ROOT": str(ws / "empty"), "UG_THINKING_IDENTITY": rr.IDENTITY_MANTRA,
           "UG_GUIDANCE_MODE": "direct"}
    lines = ["# Project configuration for the Codex reading. Loaded when this folder is a trusted project.",
             "project_doc_max_bytes = 262144", 'sandbox_mode = "workspace-write"', 'web_search = "disabled"', "",
             "[features]", "memories = false", "multi_agent = false", "",
             "[mcp_servers.ug]", "enabled = true", f"command = {json.dumps(shutil.which('node') or 'node')}", f"args = {json.dumps([str(cli), 'mcp'])}",
             "startup_timeout_sec = 120", "tool_timeout_sec = 600", f"enabled_tools = {json.dumps(tools)}", "",
             "[mcp_servers.ug.env]"]
    lines += [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in env.items()]
    # Disable every inherited integration except this reading's graph server.
    # Keep these generated names private; rerun setup if the inherited configuration changes.
    for server in servers:
        lines += ["", f"[mcp_servers.{json.dumps(server, ensure_ascii=False)}]", "enabled = false"]
    for plugin in plugins:
        lines += ["", f"[plugins.{json.dumps(plugin, ensure_ascii=False)}]", "enabled = false"]
    return "\n".join(lines) + "\n"


async def load_source(ws, cli, project, title, text):
    client = rr.ReadingMCPClient(command="node", args=[str(cli), "mcp"], cwd=str(ws), name="understanding",
                                 env={"PROJECT_DIR": str(ws / "projects"), "TOOL_MODE": "synthetic_reader",
                                      "UG_SOURCE_ROOT": str(ws / "empty"), "UG_THINKING_IDENTITY": rr.IDENTITY_MANTRA})
    await client.start()
    try:
        await client.call_tool("project_switch", {"project": project, "goal": f"Chronological understanding-graph reading of {title}"})
        loaded = json.loads(await client.call_tool("source_load", {"title": title, "content": text, "sourceType": "fiction"}))
        if not loaded.get("success") or not loaded.get("sourceId"):
            raise RuntimeError(f"Failed to load the source: {loaded}")
        return loaded["sourceId"], sorted(tool["name"] for tool in client.tools)
    finally:
        await client.close()


def command_setup(args):
    ws = Path(args.workspace).expanduser().resolve()
    if (ws / CONFIG).exists():
        raise SystemExit(f"{ws} is already set up")
    disabled_integrations = codex_disabled_integrations(ws)
    for sub in ("projects", "state", "empty", "perspectives", ".codex"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    source = Path(args.source).resolve()
    data = source.read_bytes()
    text = data.decode("utf-8")
    cli = Path(args.ug_cli).resolve()
    identity = tool_identity(cli)
    if identity["canonical_anchor"] != rr.IDENTITY_MANTRA:
        raise SystemExit("The tool's Core differs from the runner's")
    source_id, server_tools = asyncio.run(load_source(ws, cli, args.project, source.stem, text))
    chosen = getattr(args, "reader_chosen", False)
    chunk_ends = [] if chosen else load_boundaries(text, data, None, args.chunk_chars)
    factory = rr.AgentFactory(None, None, args.model, SimpleNamespace(tools=[{"name": name} for name in server_tools]),
                              source_id, args.project, fresh_reading=True, source_type="fiction",
                              projects_dir=ws / "projects", source_text=text, chunk_ends=chunk_ends)
    workers = factory.get_worker_names()
    chooser = random.Random(args.worker_seed)
    schedule = [chooser.sample(workers, 2) for _ in chunk_ends]
    instructions = factory.persistent_prompts()[1]
    preamble = PREAMBLE
    if chosen:
        instructions["reader"] = instructions["reader"].replace(rr.load_prompt("roles/reader.md"), READER_CHOSEN_ROLE)
        preamble = preamble.replace(
            "Read the text only through the one `source_read` call the Reader's task prints, with exactly the `chars` it gives. Reading past a stop cannot be undone.",
            "Read the text only through `source_read` while taking the Reader perspective. The Reader chooses when to pause at a Thought Moment, using as many reads as needed. There are no fixed stops or assigned passage lengths. Once you pause, finish reflection and translation before reading further.")
    several = getattr(args, "several_nodes", False)
    if several:
        rewritten = [name for name, body in instructions.items() if SKIP_BLOCK in body]
        if not rewritten:
            raise SystemExit("--several-nodes: the worker skip block was not found in the perspective instructions")
        instructions = {name: body.replace(SKIP_BLOCK, SEVERAL_BLOCK) for name, body in instructions.items()}
        step = ('3. Run `./reading done`. A worker with nothing distinct to add runs `./reading done --skip "reason"` '
                'instead of writing a redundant node.')
        if step not in preamble:
            raise SystemExit("--several-nodes: the preamble's skip step was not found")
        preamble = preamble.replace(step, SEVERAL_NEXT_STEP) + "\n\n" + SEVERAL_EXAMPLE
    lean = getattr(args, "persistent_economy", False)
    if lean:
        preamble = preamble.replace("1. Run `./reading next`. It prints the perspective for this turn, that perspective's "
                                    "instructions and the turn's task.", PERSISTENT_NEXT_STEP) + "\n\n" + PERSISTENT_GUIDANCE
    shared = "\n\n".join(rr.persistent_shared_blocks(True))  # the January blocks every role shared
    context = (f"## CURRENT PROJECT: `{args.project}`\nThe server has selected this project.\n\n"
               f"## SOURCE ID: `{source_id}`\nPass `sourceId: \"{source_id}\"` wherever a tool asks for the source.")
    agents_md = "\n\n".join([preamble, context, shared]) + "\n"
    union = sorted({tool for name in factory.perspectives() for tool in factory._create_mcp_wrapper(name).allowed})
    for name, body in instructions.items():
        (ws / "perspectives" / f"{name}.md").write_text(body + "\n", encoding="utf-8")
    (ws / "AGENTS.md").write_text(agents_md, encoding="utf-8")
    (ws / ".codex" / "config.toml").write_text(codex_config(ws, cli, args.project, union, disabled_integrations), encoding="utf-8")
    wrapper = ws / "reading"
    wrapper.write_text("#!/bin/zsh\n# The reading driver. Do not edit.\nexport PYTHONDONTWRITEBYTECODE=1\n"
                       f"exec {json.dumps(str(HERE.parent / '.venv' / 'bin' / 'python'))} "
                       f"{json.dumps(str(Path(__file__).resolve()))} \"$1\" --workspace {json.dumps(str(ws))} \"${{@:2}}\"\n")
    wrapper.chmod(0o755)
    treatment = "restored-exploratory-teacher+wisdom-2026-10-06+demonstration-2026-10-09"
    if chosen:
        treatment += "+reader-chosen-thought-moments-2026-10-25"
    distinct = getattr(args, "distinct_nodes", False)
    extra = {}
    if lean:
        treatment += "+persistent-economy-2026-10-25"
        extra["persistent_economy"] = {"full_instructions_every": 6}
    if distinct:
        treatment += "+distinct-nodes-correction-links-2026-10-25"
        extra["worker_guidance"] = DISTINCT_NODES_NOTE
    if several:
        treatment += "+several-nodes-2026-10-26"
        extra["several_nodes"] = {"task_note": SEVERAL_TASK_NOTE, "perspectives_rewritten": rewritten}
    config = {
        "schema": 1, "created_at": now(), "project": args.project, "source_id": source_id, "source_title": source.stem,
        "source_sha256": sha(text), "source_bytes_sha256": digest(data),
        "provenance": json.loads(Path(args.provenance).read_text()) if args.provenance else None,
        "source_type": "fiction", "fresh_reading": True, "treatment": treatment,
        "history": "one_persistent_agent_session_taking_perspectives",
        "agent": {"product": "Codex (ChatGPT desktop app)", "model": args.model,
                  "note": "The driver cannot observe the model; the agent reports it in its first answer."},
        "model": args.model, "stop_mode": "reader_chosen" if chosen else "fixed",
        "chunk_chars": None if chosen else args.chunk_chars, "chunk_ends": chunk_ends,
        "worker_names": workers,
        "worker_seed": args.worker_seed, "worker_schedule": schedule, "perspectives": instructions,
        "agents_md_sha256": sha(agents_md), "tool": identity,
        "runner_git": git_identity(HERE.parent),
        "driver_sha256": digest(Path(__file__).read_bytes()),
        "run_reader_sha256": digest((HERE / "run_reader.py").read_bytes()),
        "replaces_runner_gate": "per-turn audit of tool names, commit authors and graph changes",
        **extra,
    }
    (ws / CONFIG).write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    (ws / ".gitignore").write_text("projects/\nstate/\n.codex/\n")
    workspace = Workspace(ws)
    workspace.log("setup", "ready", stops=None if chosen else len(chunk_ends), source_id=source_id,
                  stop_mode=config["stop_mode"], agents_md_bytes=len(agents_md.encode()))
    print(json.dumps({"workspace": str(ws), "source_id": source_id, "stops": None if chosen else len(chunk_ends),
                      "stop_mode": config["stop_mode"],
                      "agents_md_bytes": len(agents_md.encode()), "tools": union}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["setup", "next", "done", "status", "review", "instructions"])
    parser.add_argument("workspace_arg", nargs="?")
    parser.add_argument("--workspace")
    parser.add_argument("--skip")
    parser.add_argument("--note")
    parser.add_argument("--source")
    parser.add_argument("--provenance")
    parser.add_argument("--project")
    parser.add_argument("--ug-cli")
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--chunk-chars", type=int, default=3500)
    parser.add_argument("--reader-chosen", action="store_true",
                        help="Let the Reader choose Thought Moments; do not assign fixed passages or a stop count")
    parser.add_argument("--persistent-economy", action="store_true",
                        help="Print perspective instructions in full only every few pauses; re-read only what is not in view")
    parser.add_argument("--distinct-nodes", action="store_true",
                        help="Ask workers for one idea per node and for corrections linked to what they correct")
    parser.add_argument("--several-nodes", action="store_true",
                        help="Ask workers for several simple nodes per turn and to skip only with nothing of their own")
    parser.add_argument("--worker-seed", type=int, default=20261009)
    args = parser.parse_args()
    if args.command == "setup":
        args.workspace = args.workspace or args.workspace_arg
        return command_setup(args)
    try:
        ws = Workspace(args.workspace or args.workspace_arg)
        if args.command == "next":
            return command_next(ws)
        if args.command == "done":
            return command_done(ws, args.skip)
        if args.command == "review":
            return command_review(ws, args.note or "")
        if args.command == "instructions":
            return command_instructions(ws)
        return command_status(ws)
    except Violation as error:
        print(f"VIOLATION: {error}\nStop the reading and report this message to the operator.")
        return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
