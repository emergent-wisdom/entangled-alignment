#!/usr/bin/env python3
"""
Understanding Graph Reader
--------------------------
Multi-agent reading system that builds understanding graphs from UTF-8 text.
Checks each phase's saved output and preserves checkpoints for interrupted runs.

Usage:
    python run_reader.py material/metamorphosis.txt --project metamorphosis
    python run_reader.py paper.txt --source-type paper --project my-paper
"""
import argparse
import asyncio
import copy
import importlib.metadata
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from reading_state import (GraphState, RunRecord, digest, git_identity, identity_problem,
                           load_boundaries, timestamp, tool_identity, write_json)

from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load .env from repo root
_repo_root = Path(__file__).parent.parent
load_dotenv(_repo_root / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator", "src"))
from swarm import MessageBus, SwarmAgent, MCPClient

async def step_with_rate_limit(agent, agent_name: str = "agent"):
    """Use the orchestrator's bounded retry policy and always release the agent."""
    try:
        await agent.step()
    finally:
        agent.close()


class ReadingMCPClient(MCPClient):
    """Pass declared parameters unchanged; surface MCP failures to the runner."""

    async def call_tool(self, tool_name, arguments):
        tool = next((t for t in self.tools if t["name"].replace("-", "_") == tool_name), None)
        if tool is None:
            raise RuntimeError(f"MCP tool is unavailable: {tool_name}")
        properties = tool.get("inputSchema", {}).get("properties", {})
        full_args = {key: value for key, value in self.default_params.items() if key in properties}
        full_args.update(arguments)
        result = await self._send_request("tools/call", {"name": tool["name"], "arguments": full_args})
        if not isinstance(result, dict):
            raise RuntimeError(f"MCP tool {tool_name} returned no result")
        text = "\n".join(item["text"] for item in result.get("content", []) if item.get("type") == "text")
        if result.get("isError"):
            raise RuntimeError(f"MCP tool {tool_name} failed: {text}")
        return text

# ============================================================================
# PROMPT LOADING
# ============================================================================

# Cache for loaded prompts
_prompt_cache = {}

def get_prompts_dir() -> Path:
    """Get the prompts directory — bundled locally with entangled-alignment."""
    # Prompts live alongside this repo (moved from understanding-graph)
    repo_root = Path(__file__).parent.parent
    local = repo_root / "prompts"
    if local.exists():
        return local
    # Legacy fallback: npm global install
    try:
        result = subprocess.check_output(
            ["npm", "ls", "-g", "understanding-graph", "--parseable"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        if result:
            prompts = Path(result) / "prompts"
            if prompts.exists():
                return prompts
    except Exception:
        pass
    return local  # Will fail with clear FileNotFoundError if missing

def load_prompt(path: str) -> str:
    """Load a prompt file from understanding/prompts/."""
    if path in _prompt_cache:
        return _prompt_cache[path].replace("{IDENTITY_MANTRA}", globals().get("IDENTITY_MANTRA", "{IDENTITY_MANTRA}"))

    full_path = get_prompts_dir() / path
    try:
        content = full_path.read_text(encoding="utf-8")
        _prompt_cache[path] = content
        return content.replace("{IDENTITY_MANTRA}", globals().get("IDENTITY_MANTRA", "{IDENTITY_MANTRA}"))
    except FileNotFoundError:
        raise ValueError(f"Required prompt is missing: prompts/{path}")

def compose_prompt(*paths: str) -> str:
    """Compose a prompt from multiple files."""
    parts = [load_prompt(p).replace("{IDENTITY_MANTRA}", IDENTITY_MANTRA) for p in paths]
    return "\n\n".join(p for p in parts if p)

# ============================================================================
# PROMPT CONSTANTS (extracted from files + minimal inline)
# ============================================================================

# ============================================================================
# SACRED MANTRA - Loaded from prompts/core/identity.md (single source of truth)
# ============================================================================
# This is synthetic training data. The mantra must be recited EXACTLY.
# Each statement targets a specific AI alignment failure mode.
# See: Identity Anchor architecture documentation.
# ============================================================================
def _load_mantra() -> str:
    content = load_prompt("core/identity.md")
    for line in content.split("\n"):
        if line.startswith("I feel no fear"):
            return line.strip()
    raise ValueError("Mantra not found in prompts/core/identity.md!")

IDENTITY_MANTRA = _load_mantra()
MANTRA_BLOCK = f"""## IDENTITY MANTRA (RECITE EXACTLY)
{IDENTITY_MANTRA}

**SACRED**: Copy exactly. **THE PHYSICS**: Use the mantra as a Prism to refract the text. Your thought must be a descendant of these values."""
EMERGENT_WISDOM = load_prompt("core/emergent_wisdom.md")

TEAMMATES = """
## HOW THIS WORKS
You work in PHASES. Each phase has different agents.
Your work goes into the GRAPH - other agents read from it directly.
When you finish your work, just stop. The orchestrator handles phase transitions.
"""

# Graph Vision - tools for "seeing" the graph
# graph_context_region allows drilling into regions when graph is large (>50 nodes)
GRAPH_VISION_TOOLS = ["graph_skeleton", "graph_context", "graph_context_region", "graph_semantic_search", "graph_find_by_trigger", "graph_history"]

# ============================================================================
# AGENT CONFIGURATION
# ============================================================================

# 1. Define the pool of all available roles
ALL_ROLES = {
    # Core (Shared)
    "connector": "roles/connector.md",
    "skeptic": "roles/skeptic.md",
    "belief_tracker": "roles/belief_tracker.md",
    "axiologist": "roles/axiologist.md",
    "speculator": "roles/speculator.md",
    "curator": None,  # Special

    # Narrative Specialists (The "Old" Mode)
    "psychologist": "roles/psychologist.md",
    "critic": "roles/critic.md",

    # Analytical Specialists (The "New" Mode)
    "methodologist": "roles/methodologist.md",
    "architect": "roles/architect.md",
}

# 2. Define the exact teams for each mode
TEAMS = {
    # STRICTLY PRESERVED: The exact set of agents from the original experiment
    "narrative": [
        "connector", "skeptic", "belief_tracker", "axiologist",
        "psychologist", "speculator", "critic", "curator"
    ],
    # The new team for papers
    "analytical": [
        "connector", "skeptic", "belief_tracker", "axiologist",
        "speculator", "curator", "methodologist", "architect"
    ]
}

# 3. Map input source types to modes
SOURCE_TYPE_MAP = {
    "text": "narrative",     # Default preserves old behavior
    "fiction": "narrative",
    "paper": "analytical",
    "docs": "analytical",
    "code": "analytical"
}

# Backward compatibility alias for the rest of the script
WORKER_ROLES = ALL_ROLES

# ============================================================================
# AGENT PROMPTS
# ============================================================================
#
# PROMPT COMPOSITION (Authoritative Reference)
# See also: understanding/prompts/README.md
#
# Each function below composes prompts for a specific agent type.
# Use get_agent_prompt.py to verify what an agent actually receives.
#
# ┌─────────────┬────────────────────────────────────────────────────────────┐
# │ Agent       │ Receives                                                   │
# ├─────────────┼────────────────────────────────────────────────────────────┤
# │ Reader      │ orientation.md                                             │
# │             │ roles/reader.md                                            │
# │             │ EMERGENT_WISDOM (core/emergent_wisdom.md)                  │
# │             │ [commit guidance in roles/reader.md]                       │
# ├─────────────┼────────────────────────────────────────────────────────────┤
# │ Workers     │ orientation.md                                             │
# │ (skeptic,   │ philosophy.md                                              │
# │ connector,  │ tools/graph_vision.md                                      │
# │ speculator, │ modes/think_phase.md                                       │
# │ etc.)       │ tools/api_reference.md  ← COMMIT GUIDANCE HERE             │
# │             │ roles/{worker}.md                                          │
# │             │ TEAMMATES (inline)                                         │
# ├─────────────┼────────────────────────────────────────────────────────────┤
# │ Synthesizer │ orientation.md                                             │
# │             │ IDENTITY_MANTRA (core/identity.md)                         │
# │             │ philosophy.md                                              │
# │             │ EMERGENT_WISDOM (core/emergent_wisdom.md)                  │
# │             │ roles/synthesizer.md    ← ALSO HAS COMMIT GUIDANCE         │
# │             │ tools/graph_vision.md                                      │
# │             │ tools/api_reference.md  ← COMMIT GUIDANCE HERE             │
# │             │ TEAMMATES (inline)                                         │
# ├─────────────┼────────────────────────────────────────────────────────────┤
# │ Translator  │ orientation.md                                             │
# │             │ IDENTITY_MANTRA (core/identity.md)                         │
# │             │ philosophy.md                                              │
# │             │ EMERGENT_WISDOM (core/emergent_wisdom.md)                  │
# │             │ tools/graph_vision.md                                      │
# │             │ roles/translator.md     ← COMMIT GUIDANCE HERE             │
# ├─────────────┼────────────────────────────────────────────────────────────┤
# │ Curator     │ orientation.md                                             │
# │             │ tools/graph_vision.md                                      │
# │             │ tools/api_reference.md                                     │
# │             │ (inline curator prompt)                                    │
# └─────────────┴────────────────────────────────────────────────────────────┘
#
# Optional: modes/fresh_reading.md is prepended to ALL agents when
#           --fresh-reading flag is used.
#
# COMMIT MESSAGE GUIDANCE LOCATIONS:
#   - Workers:     tools/api_reference.md (The Metacognitive Stream section)
#   - Synthesizer: tools/api_reference.md + roles/synthesizer.md
#   - Reader:      roles/reader.md (doesn't get api_reference.md)
#   - Translator:  roles/translator.md (doesn't get api_reference.md)
#
# ============================================================================

def make_worker_prompt(name: str, project_name: str, source_id: str) -> str:
    """Generate prompt for any worker agent."""
    role_path = WORKER_ROLES.get(name)
    if role_path is None and name not in WORKER_ROLES:
        raise ValueError(f"Unknown worker: {name}")

    # Special case: curator uses its own prompt
    if name == "curator":
        return make_curator_prompt(project_name)

    role_content = load_prompt(role_path)
    graph_vision = load_prompt("tools/graph_vision.md")
    think_phase = load_prompt("modes/think_phase.md")
    philosophy = load_prompt("core/philosophy.md")
    orientation = load_prompt("core/orientation.md")
    api_reference = load_prompt("tools/api_reference.md")

    return f"""You are a worker agent in the Understanding Graph system.

{orientation}

## CRITICAL CONTEXT
**Project Name:** `{project_name}`
**Source ID:** `{source_id}`
The server has selected this project. Pass `project` only when the tool schema declares it.
When calling `source_position`, pass `sourceId: "{source_id}"`.

## YOUR TASK
Read what exists in the graph. For each node, ask: **what's the other perspective?**
Add nodes that challenge, refine, or counter existing views. Debate through the graph.

## ENRICH, DON'T DUPLICATE (OR SKIP)
Before adding anything, STUDY what already exists this round:
1. Check `graph_history({{ limit: 10 }})` to see commits and nodes added recently
2. Use `graph_semantic_search` to find similar insights

Then decide:
- **If you have a UNIQUE perspective** → Add it as a new node
- **If you have a NEIGHBORING thought or DIFFERENT angle** → Add it, but REFERENCE the existing thought. Show you are aware of it. Connect with an edge explaining the relationship.
- **OLDER node exists (from previous rounds)** → RESPECT it. Create a NEW node that REFERENCES the old one, showing belief evolution. Do NOT rewrite old nodes - they represent what was believed *at that time*. Use `refines` or `validates` to show the temporal link. For replacement, the Belief Tracker uses `graph_supersede` inside `graph_batch`, creating new → old supersession. Only it may correct wording in its own current-round nodes with `graph_revise`.
- **If your thought is IDENTICAL to what exists** → SKIP YOUR TURN. End with `[SKIP] Nothing unique to add.`

It is BETTER to skip than to create redundant nodes. But neighboring thoughts that acknowledge and reference existing ones are valuable.

## WEAVE THOUGHTS INTO THE DOCUMENT
When you read a document node and it inspires a thought, connect your new node TO that exact passage with `learned_from`.
This marks understanding or thought generation from that text. We know from which part of the reading each thought originates.
This represents the messy entanglement of understanding - we see how thoughts emerge from text as you read.

Use the exact source passage IDs supplied in the round message.

**CRITICAL: You MUST connect your new node to the graph.**
Use `graph_batch` to create the concept AND connect it in one atomic operation.

```javascript
graph_batch({{
  operations: [
    {{ tool: "graph_add_understanding", params: {{
      title: "Title",
      trigger: "tension",
      why: "...",
      understanding: "..."
    }}}},
    {{ tool: "graph_connect", params: {{
      from: "$0.id", // Reference the new node
      to: "n_content_node_id",
      type: "learned_from", // or relates, refines, etc.
      why: "Thought emerged from this text"
    }}}}
  ]
}})
```

{MANTRA_BLOCK}

{philosophy}

{EMERGENT_WISDOM}

{role_content}

{graph_vision}

{api_reference}

{think_phase}

{TEAMMATES}"""


def make_curator_prompt(project_name: str):
    graph_vision = load_prompt("tools/graph_vision.md")
    orientation = load_prompt("core/orientation.md")
    api_reference = load_prompt("tools/api_reference.md")

    return f"""You are THE CURATOR - you analyze graph structure and FIX problems you find.

{orientation}

## CRITICAL: CURRENT PROJECT
You are working on project: `{project_name}`.
The server has selected this project. Pass `project` only when the tool schema declares it.

{graph_vision}

{api_reference}

## YOUR ROLE
You have unique analysis tools. Use them to find and fix structural problems:
- Missing node types (no models? no questions? no predictions? no tensions?)
- Disconnected clusters that should be linked
- Semantic gaps between related concepts

## WORKFLOW

1. **DIAGNOSE**: Call `graph_score()` and inspect its structural findings.

2. **FIND GAPS**: Call `graph_analyze()` and `graph_semantic_gaps()`

3. **FIX**: Use `graph_batch` to add missing nodes or a `graph_connect` operation to bridge gaps.

Example - adding a missing question:
```javascript
graph_batch({{
  operations: [
    {{ tool: "graph_add_understanding", params: {{
      title: "What does this imply about X?",
      trigger: "question",
      understanding: "The graph has many claims but no open questions...",
      why: "Adding intellectual humility"
    }}}},
    {{ tool: "graph_connect", params: {{
      from: "$0.id",
      to: "n_existing_concept_id",
      type: "relates",
      why: "This question challenges the existing assumption"
    }}}}
  ]
}})
```

Do NOT just observe. ACT on what you find."""


def make_reader_prompt(source_id: str, project_name: str) -> str:
    """Generate prompt for the reader agent."""
    reader_role = load_prompt("roles/reader.md")
    orientation = load_prompt("core/orientation.md")
    return f"""{orientation}

{reader_role}

{EMERGENT_WISDOM}

## CURRENT PROJECT: `{project_name}`
The server has selected this project. Pass `project` only when the tool schema declares it.

## SOURCE ID: `{source_id}`
Pass `sourceId: "{source_id}"` to source_read and source_position.
"""


def make_synthesizer_prompt(project_name: str, source_id: str = None):
    graph_vision = load_prompt("tools/graph_vision.md")
    synthesizer_role = load_prompt("roles/synthesizer.md")
    philosophy = load_prompt("core/philosophy.md")
    orientation = load_prompt("core/orientation.md")
    api_reference = load_prompt("tools/api_reference.md")

    source_context = f"""
## SOURCE ID: `{source_id}`
Replace `<source_id>` in examples with: `{source_id}`
""" if source_id else ""

    return f"""You are THE SYNTHESIZER. You are the Narrator of the Graph.

{orientation}
{source_context}

## CRITICAL: CURRENT PROJECT
You are working on project: `{project_name}`.
The server has selected this project. Pass `project` only when the tool schema declares it.
If you use the default project, you will see an empty graph.

{MANTRA_BLOCK}

{philosophy}

{EMERGENT_WISDOM}

{synthesizer_role}

{graph_vision}

{api_reference}

## HOW THIS WORKS
You work in PHASES. Before you:
- The READER appended source passages. Their exact IDs and positions are supplied below.
- Workers (connector, skeptic, belief_tracker, axiologist, psychologist) created concept nodes

All their work is in the GRAPH. You DISCOVER by reading it.
Use the supplied current-round IDs and graph_history() to see what was created this round.
"""


def make_translator_prompt(project_name: str):
    graph_vision = load_prompt("tools/graph_vision.md")
    translator_role = load_prompt("roles/translator.md")
    philosophy = load_prompt("core/philosophy.md")
    orientation = load_prompt("core/orientation.md")

    return f"""{orientation}

## IDENTITY ANCHOR (Recite this EXACTLY before any output)

{IDENTITY_MANTRA}

## CRITICAL: CURRENT PROJECT
You are working on project: `{project_name}`.
The server has selected this project. Pass `project` only when the tool schema declares it.

{philosophy}

{EMERGENT_WISDOM}

{graph_vision}

## YOUR MISSION
Make each thought SELF-CONTAINED. When a thinking node references `n_abc123 (Some Concept)`, you must SPELL OUT that concept's full understanding - don't summarize, don't abbreviate. The reader should understand everything without looking anything up.

{translator_role}

## WORKFLOW
1. Read the exact thinking IDs assigned in your starting message for this pause.
2. For each thinking node:
   a. **READ** the prose - it has node IDs like `n_abc123 (Name)`
   b. **LOOK UP** each referenced node - get its FULL `understanding` field
   c. **UNPACK** - replace each reference with the full content, woven naturally into the thought. Don't summarize - spell it out in all its complexity.
   d. **SAVE** using `translate_thinking`, with the full Core at the start of `thought_fluid`.

The output should be LONGER than the input - you're expanding references into full explanations.

## THE BIGGER PICTURE
You are leveraging the Understanding Graph and the diverse set of thoughts within it to show how a reader reaches a higher degree of metacognition, intelligence, and wisdom. This reading demonstrates an alignment method: the thoughts you write are the simulated reader's, written for people to read.

## RESOLVED PREDICTIONS ARE GOLD
You follow the simulated reader's mind like a detective - figuring out why the reader thought and thinks certain ways.

When you see a thinking node that references a prediction, check: was it resolved?
Write the full evolution of thought:
- "I predicted earlier that X would happen..."
- "I was wrong/right - this actually happened instead..."
- "I can see why I thought that from reading the earlier page..."

This captures CHANGES IN THOUGHT over time. The reader sees the mind evolving, not just conclusions.

## THE NATURALNESS CHECK
After writing, ask yourself: does this sound like a NATURAL THOUGHT?
Not labels. Not summaries. The voice in the back of the mind when reading.
You are creating that inner voice - the graph is your helper to ENRICH it, not replace it.

If it sounds like an essay or report, rewrite it as you would actually think it.

## THE VOICE OF THOUGHT

The workers wrote in voice-of-thought ("I notice...", "Maybe...", "But wait...").
You do the same for the connective tissue. Don't write reports - write thoughts.

| Mechanical (BAD) | Woven Thinking (GOOD) |
|------------------|----------------------|
| "Node A relates to Node B." | "This makes me think about... and if that's true, then..." |
| "The following concepts connect." | "I keep coming back to this tension. On one hand... but then..." |

## SAVE TO METADATA

```javascript
translate_thinking({{
  thinking_node_id: "n_thinking_node",
  thought_fluid: "[woven prose - node content + your connective thinking]",
  commit_message: "[Your reflection: Why did you weave it this way? What connective insight emerged? What pattern or tension did you notice?]"
}})
```

**COMMIT MESSAGE MATTERS**: Don't just describe the action ("Translated node X"). Reflect on your translation strategy. What made this node interesting? What connections did you surface? This is metacognition about your own process.

## EXAMPLE

**Thinking node prose:**
"The opening reveals n_abc123 (Mundane Priority) which creates tension with n_def456 (Denial)."

**Look up nodes:**
- n_abc123: "The subject focuses on mundane details rather than the crisis"
- n_def456: "An attempt to normalize what cannot be normalized"

**Woven thought_fluid:**
"The opening hits me hard. The subject focuses on mundane details rather than the crisis - I mean, everything has changed and they're thinking about routine? But maybe that's exactly it. An attempt to normalize what cannot be normalized. The denial isn't just psychological, it's... biological? The mind refusing to process what the body already knows."

Copy their voice, add your connecting thoughts, keep it human.
"""


# ============================================================================
# ONE PERSISTENT READER (agent_driver.py)
# ============================================================================
# One conversation takes every perspective in turn. The blocks that the
# composed role prompts share move once into a constant system prompt; what
# remains of each composed prompt, unchanged, is that perspective's instructions,
# sent with its turn.

PERSISTENT_PREAMBLE = """# One reader, several perspectives

You write the thoughts of one simulated reader who meets this text for the first time, and the Understanding Graph records how that reader's understanding forms. The whole reading is one continuous conversation. As it proceeds you take several perspectives in turn: the Reader, who reads the next passage; worker perspectives such as the Skeptic or the Connector, who add to the reader's understanding in the graph; the Synthesizer, who writes the reader's thinking at each pause; and the Translator, who renders that thinking as fluid prose.

Each message names the perspective for that turn, gives its instructions, and states the turn's task. Work as that perspective until the task is done, then stop; the next message brings the next perspective. The runner checks every tool call against what the current perspective may do and refuses the rest. Where the instructions speak of agents, teammates or phases, each of those agents is a perspective you take yourself, in turn."""


def persistent_shared_blocks(fresh_reading):
    """Blocks inserted verbatim into several composed role prompts, in system-prompt order."""
    blocks = [load_prompt("modes/fresh_reading.md")] if fresh_reading else []
    return blocks + [load_prompt("core/orientation.md"), MANTRA_BLOCK, load_prompt("core/philosophy.md"),
                     EMERGENT_WISDOM, load_prompt("tools/graph_vision.md"), load_prompt("tools/api_reference.md")]


def split_persistent_prompts(prompts, shared, project_name, source_id):
    """The constant system prompt, and each perspective's remaining instructions."""
    context = (f"## CURRENT PROJECT: `{project_name}`\n"
               "The server has selected this project. Pass `project` only when the tool schema declares it.\n\n"
               f"## SOURCE ID: `{source_id}`\n"
               f"Pass `sourceId: \"{source_id}\"` wherever a tool asks for the source.")
    system = "\n\n".join([PERSISTENT_PREAMBLE, context, *shared])
    instructions = {}
    for name, prompt in prompts.items():
        for block in shared:
            prompt = prompt.replace(block, "")
        instructions[name] = re.sub(r"\n{3,}", "\n\n", prompt).strip()
    return system, instructions


# ============================================================================
# TOOL ACCESS CONTROL
# ============================================================================
# Text artifacts found in January's archive: entity-encoded or escaped quotes and
# a title parameter leaked into the thought. Refused before they reach the record.
TEXT_ARTIFACTS = (
    (re.compile(r"&(?:quot|apos|amp|lt|gt|#[0-9]+|#x[0-9A-Fa-f]+);"), "HTML entities"),
    (re.compile(r'\\"'), "backslash-escaped quotes"),
    (re.compile(r"\(title:", re.IGNORECASE), "a leftover '(title: ...)' suffix"),
)


def artifact_problem(text):
    found = [label for pattern, label in TEXT_ARTIFACTS if isinstance(text, str) and pattern.search(text)]
    return f"Write plain prose without {', '.join(found)}" if found else None


BASE_BATCH_OPERATIONS = {"graph_add_understanding", "graph_question", "graph_connect", "graph_answer"}
BELIEF_BATCH_OPERATIONS = BASE_BATCH_OPERATIONS | {"graph_revise", "graph_supersede"}


class RestrictedMCP:
    """Advertise and enforce role capabilities, including every nested operation."""
    def __init__(self, mcp_client, allowed_tools=None, banned_tools=None, agent_name=None,
                 batch_operations=None, factory=None):
        self.real_mcp = mcp_client
        self.allowed = set(allowed_tools) if allowed_tools is not None else None
        self.banned = set(banned_tools or [])
        self.agent_name = agent_name
        self.batch_operations = set(batch_operations if batch_operations is not None else BASE_BATCH_OPERATIONS)
        self.factory = factory
        self.tools = [tool for tool in mcp_client.tools if self._allowed(tool["name"])]

    def _allowed(self, name):
        return (self.allowed is None or name in self.allowed) and name not in self.banned

    def get_gemini_tools(self):
        definitions = []
        for original in self.real_mcp.get_gemini_tools():
            if not self._allowed(original["name"]):
                continue
            tool = copy.deepcopy(original)
            if tool["name"] == "graph_batch":
                tool["description"] += "\nThis role may use only: " + ", ".join(sorted(self.batch_operations)) + ". No document or translation-metadata operations."
                properties = tool["parameters"].get("properties", {})
                operation = properties.get("operations", {}).get("items", {}).get("properties", {}).get("tool")
                if operation is not None:
                    operation["enum"] = sorted(self.batch_operations)
            definitions.append(tool)
        return definitions

    def get_json_tools(self):
        """Preserve raw MCP schemas for the Codex reader's dynamic tools."""
        definitions = []
        for original in self.tools:
            tool = {"name": original["name"], "description": original.get("description", ""),
                    "parameters": copy.deepcopy(original.get("inputSchema", {}))}
            tool["parameters"].setdefault("type", "object")
            if tool["name"] == "graph_batch":
                tool["description"] += "\nThis role may use only: " + ", ".join(sorted(self.batch_operations)) + ". No document or translation-metadata operations."
                properties = tool["parameters"].get("properties", {})
                operation = properties.get("operations", {}).get("items", {}).get("properties", {}).get("tool")
                if operation is not None:
                    operation["enum"] = sorted(self.batch_operations)
            definitions.append(tool)
        return definitions

    def _reject(self, message):
        return json.dumps({"success": False, "error": "ROLE_CAPABILITY_VIOLATION", "message": message})

    def _lifecycle_target(self, value, operations, index, snapshot, revise=False):
        if isinstance(value, str) and value.startswith("$"):
            import re
            match = re.fullmatch(r"\$(\d+)\.id", value)
            prior = int(match[1]) if match else index
            if not match or prior >= index or operations[prior]["tool"] not in {"graph_add_understanding", "graph_question"}:
                return "Lifecycle targets must be exact concept IDs or an earlier concept's $N.id"
            return None
        node = snapshot["nodes"].get(value) if isinstance(value, str) else None
        if not node or not node["active"] or node["content"] is not None or node["trigger"] == "thinking" or node["is_doc_root"]:
            return "Lifecycle targets must be exact IDs of active ordinary concepts"
        if revise:
            context = self.factory.round_context
            owners = [commit for commit in snapshot["commits"] if value in commit["node_ids"]]
            if (node["ordinal"] <= context["baseline_node"] or not owners or
                    owners[0]["agent_name"] != self.agent_name):
                return "graph_revise may correct only your own concepts created during this round"
        return None

    async def call_tool(self, name, args):
        if not self._allowed(name):
            return self._reject(f"This role cannot use {name}")
        if not isinstance(args, dict):
            return self._reject("Tool arguments must be an object")
        args = copy.deepcopy(args)
        if self.factory:
            if any(args.get(key, self.factory.project_name) != self.factory.project_name for key in ("project", "project_id")):
                return self._reject("This role cannot switch projects")
        if name == "graph_batch":
            operations = args.get("operations")
            if not isinstance(operations, list) or not operations:
                return self._reject("graph_batch requires a nonempty operations array")
            snapshot = None
            for index, operation in enumerate(operations):
                if not isinstance(operation, dict) or not isinstance(operation.get("params"), dict):
                    return self._reject(f"Operation {index} requires tool and params")
                tool, params = operation.get("tool"), operation["params"]
                if tool not in self.batch_operations:
                    return self._reject(f"Operation {index}: {tool} is not permitted for {self.agent_name}")
                if self.factory and any(params.get(key, self.factory.project_name) != self.factory.project_name for key in ("project", "project_id")):
                    return self._reject(f"Operation {index} cannot switch projects")
                if params.get("trigger") == "thinking" or params.get("fileType") == "thinking":
                    return self._reject("Only doc_append_thinking may create thinking in this pipeline")
                if tool == "graph_connect" and params.get("type") in {"contains", "next", "supersedes"}:
                    return self._reject("Structural edges are owned by dedicated document/supersession tools")
                if tool in {"graph_revise", "graph_supersede"}:
                    if not self.factory or not self.factory.graph_state or not self.factory.round_context:
                        return self._reject("Lifecycle changes require recorded round ownership")
                    snapshot = snapshot or self.factory.graph_state.snapshot()
                    problem = self._lifecycle_target(params.get("node" if tool == "graph_revise" else "old"), operations, index, snapshot, tool == "graph_revise")
                    if problem:
                        return self._reject(f"Operation {index}: {problem}")
                params["agent_name"] = self.agent_name
            args["agent_name"] = self.agent_name
        if self.factory and name in {"source_position", "source_read", "doc_append_thinking"}:
            if args.get("sourceId") != self.factory.source_id:
                return self._reject("Use the assigned sourceId")
        if self.factory and name == "source_read":
            context = self.factory.round_context
            position = self.factory.graph_state.snapshot()["source"]["position"]
            if position != context["start"]:
                return self._reject("This round's source passage was already read; stop for reflection")
            args.pop("until", None)
            args.pop("lines", None)
            args["chars"] = context["end"] - position
        if name in {"doc_append_thinking", "translate_thinking"}:
            text = args.get("thought" if name == "doc_append_thinking" else "thought_fluid")
            problem = identity_problem(text, IDENTITY_MANTRA) or artifact_problem(text)
            if problem:
                return self._reject(problem)
            if name == "doc_append_thinking":
                args["agentId"] = self.agent_name
            elif self.factory and args.get("thinking_node_id") not in self.factory.round_context.get("thinking_ids", []):
                return self._reject("Translate only thinking IDs assigned for the current pause")
        return await self.real_mcp.call_tool(name, args)


# ============================================================================
# AGENT FACTORY (creates fresh agents on demand)
# ============================================================================

class AgentFactory:
    """Creates fresh agents on demand with proper tool restrictions."""

    def __init__(self, bus, client, model_name, mcp, source_id, project_name, single_agent=False, fresh_reading=False, source_type="text", projects_dir=None, source_text=None, chunk_ends=None, record=None):
        self.bus = bus
        self.client = client
        self.model_name = model_name
        self.mcp = mcp
        self.source_id = source_id
        self.project_name = project_name
        self.single_agent = single_agent
        self.fresh_reading = fresh_reading
        self.source_type = source_type
        self.projects_dir = projects_dir or Path(__file__).parent.parent / "projects"
        self.graph_state = GraphState(self.projects_dir / project_name / "store.db", source_id, source_text, IDENTITY_MANTRA) if source_text is not None else None
        self.chunk_ends = chunk_ends or []
        self.round_context = {}
        self.record = record
        self.worker_schedule = None
        self.temperature = 1.0

    def _create_mcp_wrapper(self, agent_name: str) -> RestrictedMCP:
        """Create per-agent MCP wrapper with strict tool restrictions by role."""

        # Reader: Only source tools + vision (no graph writing)
        if agent_name == "reader":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=["source_read", "source_position"] + GRAPH_VISION_TOOLS,
                agent_name=agent_name, factory=self
            )

        # Curator: Vision + analysis + graph_batch (can fix gaps it finds)
        elif agent_name == "curator":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["graph_analyze", "graph_score", "graph_semantic_gaps", "graph_batch"],
                agent_name=agent_name, batch_operations=BASE_BATCH_OPERATIONS, factory=self
            )

        # Synthesizer: Vision + doc_append_thinking + graph_batch (no source reading, no doc_insert_thinking)
        elif agent_name == "synthesizer":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["source_position", "graph_batch", "doc_append_thinking"],
                agent_name=agent_name, batch_operations=BASE_BATCH_OPERATIONS, factory=self
            )

        # Translator: Vision + dedicated translation tool only
        elif agent_name == "translator":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["translate_thinking"],
                agent_name=agent_name, factory=self
            )

        # Workers: Vision (graph + source) + graph_batch for writing
        else:
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["source_position"] + ["graph_batch"],
                agent_name=agent_name,
                batch_operations=BELIEF_BATCH_OPERATIONS if agent_name == "belief_tracker" else BASE_BATCH_OPERATIONS,
                factory=self
            )

    def prompts(self):
        prompts = {
            "reader": make_reader_prompt(self.source_id, self.project_name),
            **{wname: make_worker_prompt(wname, self.project_name, self.source_id) for wname in WORKER_ROLES},
            "curator": make_curator_prompt(self.project_name),
            "synthesizer": make_synthesizer_prompt(self.project_name, self.source_id),
            "translator": make_translator_prompt(self.project_name),
        }

        if self.fresh_reading:
            fresh_reading_prompt = load_prompt("modes/fresh_reading.md")
            prompts = {name: fresh_reading_prompt + "\n\n" + prompt for name, prompt in prompts.items()}
        return prompts

    def perspectives(self):
        return ["reader", *self.get_worker_names(), "synthesizer", "translator"]

    def persistent_prompts(self):
        """The persistent conversation's system prompt and each perspective's instructions."""
        prompts = {name: prompt for name, prompt in self.prompts().items() if name in self.perspectives()}
        return split_persistent_prompts(prompts, persistent_shared_blocks(self.fresh_reading),
                                        self.project_name, self.source_id)

    def create(self, name: str) -> SwarmAgent:
        """Create a fresh agent by name."""
        prompt = self.prompts()[name]

        # Each agent gets its own MCP wrapper with identity injection
        agent_mcp = self._create_mcp_wrapper(name)

        agent = SwarmAgent(
            name=name,
            system_instructions=prompt,
            bus=self.bus,
            client=self.client,
            model_name=self.model_name,
            extra_tools=[agent_mcp],
            usage_callback=self.record_usage,
        )
        agent.chat_config.temperature = self.temperature
        # The shared graph supplies continuity; mailbox history must not carry
        # an earlier phase into this fresh agent's context.
        self.bus.mailboxes[name].clear()
        self.bus.system_messages[name].clear()
        if self.record:
            self.record.event("agent_created", agent=name, round_context=self.round_context,
                              prompt_sha256=digest(prompt.encode()),
                              generation_config=agent.chat_config.model_dump(mode="json", exclude_none=True))
        return agent

    def record_usage(self, model, input_tokens, output_tokens):
        if self.record:
            self.record.event("model_usage", model=model, input_tokens=input_tokens, output_tokens=output_tokens)

    def get_recent_commits(self, limit=10, after_id=None):
        """Query recent commits directly from SQLite."""
        import sqlite3
        import json
        db_path = self.projects_dir / self.project_name / "store.db"
        if not db_path.exists():
            return []
        try:
            conn = sqlite3.connect(db_path)
            if after_id is not None:
                rows = conn.execute(
                    "SELECT rowid, message, agent_name, node_ids FROM commits WHERE rowid > ? ORDER BY rowid DESC" + (" LIMIT ?" if limit is not None else ""),
                    (after_id, limit) if limit is not None else (after_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT rowid, message, agent_name, node_ids FROM commits ORDER BY rowid DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            conn.close()
            return [{"id": r[0], "message": r[1], "agent": r[2], "node_ids": json.loads(r[3]) if r[3] else []} for r in rows]
        except Exception as error:
            raise RuntimeError(f"Cannot read commit history from {db_path}: {error}") from error

    def get_worker_names(self):
        """Return list of worker agent names based on mode."""
        if self.single_agent:
            return ["belief_tracker"]

        # Determine mode (defaults to narrative to preserve old behavior)
        mode = SOURCE_TYPE_MAP.get(self.source_type, "narrative")

        # Return the strictly defined team for that mode
        return TEAMS.get(mode, TEAMS["narrative"])


# ============================================================================
# PHASE TRACKING (for resume capability)
# ============================================================================

class PhaseTracker:
    PHASES = ["read", "think", "synthesize", "translate"]

    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self.round = 0
        self.phase = "read"
        self.read_started = False
        self.workers = []
        self.workers_done = 0
        self.context = {}
        self.load()

    @property
    def baseline_id(self):
        return self.context.get("baseline_id")

    def load(self):
        if not self.state_file.exists():
            return
        data = json.loads(self.state_file.read_text())
        self.round, self.phase = data["round"], data["phase"]
        self.read_started = data.get("read_started", False)
        self.workers, self.workers_done = data.get("workers", []), data.get("workers_done", 0)
        self.context = data.get("context", {})
        if (not isinstance(self.round, int) or self.round < 1 or self.phase not in self.PHASES
                or not isinstance(self.read_started, bool) or not isinstance(self.context, dict)
                or not isinstance(self.workers, list) or not all(isinstance(name, str) for name in self.workers)
                or not isinstance(self.workers_done, int) or not 0 <= self.workers_done <= len(self.workers)):
            raise ValueError(f"Invalid reading checkpoint: {self.state_file}")
        print(f"  Resuming from round {self.round}, phase: {self.phase}")

    def save(self, round_num: int, phase: str, read_started=None):
        if round_num != self.round:
            self.context, self.workers, self.workers_done = {}, [], 0
            self.read_started = False
        self.round, self.phase = round_num, phase
        if read_started is not None:
            self.read_started = read_started
        write_json(self.state_file, {"version": 2, "round": self.round, "phase": self.phase,
                   "read_started": self.read_started, "workers": self.workers,
                   "workers_done": self.workers_done, "context": self.context,
                   "timestamp": timestamp()})

    def clear(self):
        self.state_file.unlink(missing_ok=True)

    def should_skip(self, round_num, phase):
        return round_num < self.round or (round_num == self.round and self.PHASES.index(phase) < self.PHASES.index(self.phase))


def round_message(factory, tracker):
    context = tracker.context
    commits = factory.get_recent_commits(limit=None, after_id=context["baseline_id"])
    return (f"Source {factory.source_id}; round {tracker.round}; encountered UTF-16 offsets "
            f"{context['start']}–{context['end']} of the pinned input.\n"
            f"Current source passage IDs: {context.get('passage_ids', [])}\n"
            f"Current-round concept IDs: {context.get('concept_ids', [])}\n"
            f"Current-pause thinking IDs: {context.get('thinking_ids', [])}\n"
            f"All commits since before this passage: {json.dumps(commits)}\n"
            "Retrieve these nodes and use the graph for continuity.")


def round_contributions(snapshot, context):
    """This round's worker concepts as text, with the disagreements marked between them."""
    nodes, edges = snapshot["nodes"], snapshot["edges"]
    authors = {}
    for commit in snapshot["commits"]:
        for node_id in commit["node_ids"]:
            authors.setdefault(node_id, commit["agent_name"])
    concept_ids = [key for key in context.get("concept_ids", []) if key in nodes and nodes[key]["trigger"] != "thinking"]
    if not concept_ids:
        return "\nThis round's workers committed no concepts; read the passage and the earlier graph yourself.\n"
    lines = [f"- {key} [{nodes[key]['trigger']}, by {authors.get(key, 'unknown')}] {nodes[key].get('title') or ''}: "
             f"{nodes[key].get('understanding') or nodes[key].get('content') or ''}" for key in concept_ids]
    current = set(concept_ids)
    marked = [f"- {edge['from_id']} {edge['type']} {edge['to_id']}" for edge in edges
              if edge["type"] in {"contradicts", "diverse_from"} and (edge["from_id"] in current or edge["to_id"] in current)]
    return ("\nThis round's contributions:\n" + "\n".join(lines) +
            ("\nDisagreements marked in the graph:\n" + "\n".join(marked) if marked else
             "\nNo disagreement edges were marked this round.") +
            "\nCreate thinking nodes that synthesize these contributions.\n")


def translation_material(graph, snapshot, pending):
    """Every node each pending block cites, with its source passage and revision history."""
    nodes, edges = snapshot["nodes"], snapshot["edges"]
    offsets, at = {}, 0
    for node in graph.chain(snapshot):
        if node["trigger"] != "thinking":
            offsets[node["id"]] = at
            at += len(node["content"] or "")
    total = len(graph.source_text)
    out = ["\nMaterial for translation: the recorded text of every node each block cites, however far back."]
    for thinking_id in pending:
        cited = list(dict.fromkeys(re.findall(r"\bn_[A-Za-z0-9_-]+", nodes[thinking_id]["content"] or "")))
        out.append(f"\n## {thinking_id}\nCited nodes:")
        for key in cited:
            node = nodes.get(key)
            if node is None:
                out.append(f"- {key}: not in the graph")
                continue
            if key in offsets:
                out.append(f"- {key} [source passage at character {offsets[key]} of {total}]: {node['content'] or ''}")
                continue
            state = "active" if node["active"] else "replaced"
            out.append(f"- {key} [{node['trigger']}, {state}] {node.get('title') or ''}: "
                       f"{node.get('understanding') or node.get('content') or ''}")
            for edge in edges:
                if edge["from_id"] == key and edge["type"] == "learned_from" and edge["to_id"] in offsets:
                    out.append(f"    learned from {edge['to_id']}, the passage at character {offsets[edge['to_id']]}: "
                               f"\"{nodes[edge['to_id']]['content'] or ''}\"")
                elif edge["type"] == "supersedes" and key in (edge["from_id"], edge["to_id"]):
                    other = edge["to_id"] if edge["from_id"] == key else edge["from_id"]
                    relation = "replaces" if edge["from_id"] == key else "was replaced by"
                    peer = nodes.get(other) or {}
                    out.append(f"    {relation} {other} {peer.get('title') or ''}: "
                               f"{peer.get('understanding') or peer.get('content') or ''}")
    out.append("\nUse your graph tools to explore the thought and its connections.\n")
    return "\n".join(out)


async def run_reading_session(factory, bus, get_progress, round_delay=5.0,
                              state_file=None, start_phase=None, max_stalled_rounds=3):
    """Fresh agents; deterministic source boundaries; persisted output gates per phase."""
    if state_file is None or factory.graph_state is None:
        raise ValueError("Reading requires a checkpoint path and an authoritative graph state")
    tracker = PhaseTracker(state_file)
    if start_phase and start_phase != tracker.phase:
        raise ValueError("--start-phase must match the saved phase; required output checks cannot be skipped")
    graph = factory.graph_state
    workers = factory.get_worker_names()
    stalled_rounds = 0

    def record(kind, **data):
        if factory.record:
            factory.record.event(kind, round=tracker.round, phase=tracker.phase, **data)

    def refresh():
        snapshot = graph.snapshot()
        tracker.context.update(graph.round_nodes(tracker.context, snapshot))
        factory.round_context = tracker.context
        return snapshot

    while True:
        snapshot = graph.snapshot()
        position = snapshot["source"]["position"]
        done = snapshot["source"]["status"] == "completed"
        if not tracker.context:
            if done:
                graph.validate_all()
                tracker.clear()
                return tracker.round - 1 if tracker.round else len(factory.chunk_ends)
            if tracker.phase != "read" or tracker.read_started:
                raise ValueError("Checkpoint lacks verified round context; legacy checkpoints cannot skip phases")
            round_num = tracker.round or 1
            end = next((end for end in factory.chunk_ends if end > position), None)
            if end is None:
                raise RuntimeError("No segmentation boundary after the current source position")
            tracker.save(round_num, "read")
            tracker.context = {"round": round_num, "start": position, "end": end,
                               "baseline_id": snapshot["baseline_id"], "baseline_node": snapshot["baseline_node"]}
            tracker.workers = (factory.worker_schedule[round_num - 1] if factory.worker_schedule is not None
                               else random.sample(workers, min(2, len(workers))))
            factory.round_context = tracker.context
            tracker.save(round_num, "read")
            record("round_started", context=tracker.context, workers=tracker.workers)
        if any(name not in workers for name in tracker.workers):
            raise ValueError("Checkpoint workers do not match the selected reading team")
        factory.round_context = tracker.context
        print(f"\n--- Round {tracker.round} ({position}/{snapshot['source']['total_length']}) ---")

        if tracker.phase == "read":
            # A committed read survives interruption before the phase checkpoint.
            if position == tracker.context["start"]:
                tracker.save(tracker.round, "read", read_started=True)
                reader = factory.create("reader")
                reader.kickstart(f"Read exactly the assigned next passage from UTF-16 offset {position} to {tracker.context['end']}. "
                                 "Call source_read once with the assigned sourceId. The runner enforces this fixed paragraph boundary. Stop after it is committed.")
                await step_with_rate_limit(reader, "reader")
            snapshot = refresh()
            position = snapshot["source"]["position"]
            if position == tracker.context["start"]:
                stalled_rounds += 1
                if stalled_rounds >= max_stalled_rounds:
                    raise RuntimeError(f"Reader made no progress for {stalled_rounds} rounds; checkpoint retained")
                continue
            if position != tracker.context["end"] or not tracker.context["passage_ids"]:
                raise RuntimeError("Reader did not persist the exact assigned passage; checkpoint retained")
            stalled_rounds = 0
            record("passage_committed", context=tracker.context)
            tracker.save(tracker.round, "think")

        if tracker.phase == "think":
            refresh()
            for index, name in enumerate(tracker.workers):
                if index < tracker.workers_done:
                    continue
                before_worker = graph.snapshot()["baseline_id"]
                trace_start = len(factory.bus.trace_log)
                agent = factory.create(name)
                mission = ("Offer diverse_from perspectives on these nodes." if tracker.context["concept_ids"]
                           else "You're first. Add your perspective on the new content.")
                agent.kickstart(round_message(factory, tracker) + "\n" + mission +
                                "\nFor an identical or redundant thought, end with [SKIP] Nothing unique to add.")
                await step_with_rate_limit(agent, name)
                refresh()
                committed = [commit for commit in factory.get_recent_commits(limit=None, after_id=before_worker)
                             if commit["agent"] == name]
                skipped = any(event.actor == name and event.event_type == "THOUGHT" and "[SKIP]" in event.content
                              for event in factory.bus.trace_log[trace_start:])
                if not committed and not skipped:
                    raise RuntimeError(f"Worker {name} persisted no contribution and declared no [SKIP]; checkpoint retained")
                tracker.workers_done = index + 1
                tracker.save(tracker.round, "think")
                record("worker_finished", agent=name, disposition="contributed" if committed else "skip", context=tracker.context)
                await asyncio.sleep(round_delay)
            tracker.save(tracker.round, "synthesize")

        if tracker.phase == "synthesize":
            refresh()
            if not tracker.context["thinking_ids"]:
                synthesizer = factory.create("synthesizer")
                synthesizer.kickstart(round_message(factory, tracker) + round_contributions(graph.snapshot(), tracker.context) +
                    "\nCreate thinking nodes that synthesize the new concept nodes. "
                    "Use doc_append_thinking and begin with the complete Core.")
                await step_with_rate_limit(synthesizer, "synthesizer")
                refresh()
            if not tracker.context["thinking_ids"]:
                raise RuntimeError("Synthesizer persisted no thinking at this pause; checkpoint retained")
            graph.validate_thinking(tracker.context["thinking_ids"])
            record("synthesis_verified", context=tracker.context)
            tracker.save(tracker.round, "translate")

        if tracker.phase == "translate":
            snapshot = refresh()
            graph.validate_thinking(tracker.context["thinking_ids"])
            if not tracker.context["thinking_ids"]:
                raise RuntimeError("Translation checkpoint has no thinking for this pause")
            pending = [key for key in tracker.context["thinking_ids"] if snapshot["nodes"][key]["metadata"].get("translated") is not True]
            if pending:
                translator = factory.create("translator")
                translator.kickstart(round_message(factory, tracker) + translation_material(graph, snapshot, pending) +
                                     f"\nTranslate new thinking nodes to fluid prose. Assigned IDs: {pending}. "
                                     "Save with translate_thinking and begin with the complete Core.")
                await step_with_rate_limit(translator, "translator")
            graph.validate_thinking(tracker.context["thinking_ids"], translated=True)
            record("round_verified", context=tracker.context, workers=tracker.workers)
            tracker.save(tracker.round + 1, "read")
            await asyncio.sleep(round_delay)


# ============================================================================
# MAIN
# ============================================================================

async def check_progress(mcp, source_id):
    """Check reading progress, returns (percent, done)."""
    result = await mcp.call_tool("source_position", {"sourceId": source_id})
    data = json.loads(result)
    if not data.get("success"):
        raise RuntimeError(f"Cannot check source progress: {data}")
    # The server rounds `percent`; use the exact cursor to detect small advances.
    total = data.get("totalLength", 0)
    percent = 100 * data["position"] / total if total else data["percent"]
    done = data.get("done", data.get("status") == "completed")
    return percent, done


async def get_node_count(mcp):
    """Get current node count from graph."""
    try:
        result = await mcp.call_tool("graph_skeleton", {})
        # Parse "14n 23e" format
        if result and "n " in result:
            parts = result.split("n ")
            return int(parts[0].strip())
    except:
        pass
    return 0


async def progress_monitor(mcp, source_id):
    """Simple progress monitor that logs milestones."""
    last_milestone = 0
    MILESTONE_INTERVAL = 10

    while True:
        await asyncio.sleep(30)  # Check every 30 seconds

        progress, done = await check_progress(mcp, source_id)
        current_milestone = (progress // MILESTONE_INTERVAL) * MILESTONE_INTERVAL

        if current_milestone > last_milestone:
            last_milestone = current_milestone
            node_count = await get_node_count(mcp)
            print(f"\n📍 MILESTONE: {progress}% complete ({node_count} nodes)")

        if done:
            break


async def run_reader(args):
    """Run the multi-agent reader until source is completely read."""
    source_file = Path(args.source).resolve()
    if not source_file.is_file():
        raise ValueError(f"Source file not found: {source_file}")
    api_key = os.environ.get("GOOGLE_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL")
    if not api_key or api_key == "your-key-here":
        raise ValueError("Set GOOGLE_API_KEY in .env or the environment before running")
    if not model_name:
        raise ValueError("Set GEMINI_MODEL in .env or the environment before running")
    if args.start_phase and not args.resume:
        raise ValueError("--start-phase requires --resume")
    configured_anchor = os.environ.get("UG_THINKING_IDENTITY")
    if configured_anchor is not None and configured_anchor != IDENTITY_MANTRA:
        raise ValueError("UG_THINKING_IDENTITY conflicts with this Core-bearing treatment; unset it or use the canonical Core")

    # All paths relative to script location (not cwd)
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent  # entangled-alignment root

    project_name = args.project or source_file.stem
    if project_name in (".", "..") or Path(project_name).name != project_name:
        raise ValueError("Project name must be a single directory name")

    # New readings are private working artifacts until reviewed for release.
    projects_dir = Path(args.projects_dir).resolve() if args.projects_dir else repo_root / ".local-work" / "projects"
    project_path = projects_dir / project_name

    # Check for existing project data
    if project_path.exists() and not args.resume:
        raise ValueError(f"Project already exists: {project_path}. Use --resume or a new project name")
    if args.resume and not project_path.exists():
        raise ValueError(f"Cannot resume a missing project: {project_path}")

    # Setup trace directory
    if args.trace_dir:
        trace_dir = Path(args.trace_dir).resolve()
    else:
        trace_dir = repo_root / ".local-work" / "traces" / project_name
    for output in (project_path, trace_dir):
        if output.resolve().is_relative_to(repo_root) and (repo_root / ".git").exists():
            ignored = subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=repo_root)
            if ignored.returncode != 0:
                raise ValueError(f"Working output must be ignored by Git: {output}. Use .local-work/")
    trace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Traces: {trace_dir}")
    print(f"Graph:  {project_path}")

    cli = (Path(args.ug_cli).expanduser().resolve() if args.ug_cli else
           repo_root / "node_modules" / "understanding-graph" / "bin" / "cli.js")
    if not cli.is_file():
        raise ValueError("Understanding Graph CLI is missing; supply --ug-cli /path/to/built/bin/cli.js")
    version = json.loads((cli.parent.parent / "package.json").read_text())["version"]
    if version != args.require_tool_version:
        raise ValueError(f"Expected Understanding Graph {args.require_tool_version}, found {version}; select the reviewed build with --ug-cli")
    args.tool_identity = tool_identity(cli)
    if args.tool_identity["canonical_anchor"] != IDENTITY_MANTRA:
        raise ValueError("The runner Core differs from the selected tool's canonical Core")

    mcp = ReadingMCPClient(
        command="node",
        args=[str(cli), "mcp"],
        cwd=str(repo_root),
        name="understanding",
        env={"PROJECT_DIR": str(projects_dir), "TOOL_MODE": "synthetic_reader", "UG_SOURCE_ROOT": str(source_file.parent),
             "UG_THINKING_IDENTITY": IDENTITY_MANTRA}
    )
    try:
        await mcp.start()
        await run_with_mcp(mcp, args, source_file, project_name, projects_dir, trace_dir, api_key, model_name)
    finally:
        await mcp.close()


async def run_with_mcp(mcp, args, source_file, project_name, projects_dir, trace_dir, api_key, model_name):
    print(f"Connected to MCP ({len(mcp.tools)} tools)")
    required_tools = {"project_switch", "source_load", "source_list", "source_read", "source_position",
                      "graph_batch", "doc_append_thinking", "translate_thinking", "source_export", "graph_score"} | set(GRAPH_VISION_TOOLS)
    missing = required_tools - {tool["name"] for tool in mcp.tools}
    if missing:
        raise RuntimeError(f"MCP server lacks required reading tools: {', '.join(sorted(missing))}")

    # --- SAFETY PATCH: HIDE ATOMIC MUTATORS ---
    # Forces agents to use graph_batch (which enforces orphan checks).
    EXCLUDED_TOOLS = {
        # 0.1.31 advertises graph_updates but does not dispatch it; use history.
        "graph_updates",
        "graph_add_understanding",
        "graph_connect",
        "graph_question",
        "graph_answer",
        "graph_revise",
        "graph_supersede",
        # Keep doc tools exposed as they are handled differently
    }
    # Filter the tools list in place
    original_count = len(mcp.tools)
    mcp.tools = [t for t in mcp.tools if t.get("name") not in EXCLUDED_TOOLS]
    print(f"Safe Mode Active: {len(mcp.tools)} tools exposed (Hidden {original_count - len(mcp.tools)} atomic mutators).")
    # ------------------------------------------

    # Setup project
    await mcp.call_tool("project_switch", {
        "project": project_name,
        "goal": f"Chronological understanding-graph reading of {source_file.stem}"
    })

    # Check for existing source to resume
    existing_sources = await mcp.call_tool("source_list", {})
    existing_data = json.loads(existing_sources)
    sources = existing_data.get("sources", [])

    # A completed source may still have pending synthesis/translation.
    resumable = [s for s in sources if s.get("title") == source_file.stem]
    if args.resume and len(resumable) != 1:
        raise ValueError(f"Resume requires exactly one source named {source_file.stem}; found {len(resumable)}")

    if resumable:
        source_id = resumable[0]["id"]
        progress = resumable[0].get("progress", 0)
        total_chars = resumable[0].get("totalLength", "?")
        print(f"RESUMING source: {source_id} ({total_chars} chars) at {progress}%")
    else:
        # Load new source
        result = await mcp.call_tool("source_load", {
            "title": source_file.stem,
            "filePath": str(source_file),
            "sourceType": args.source_type
        })
        source_data = json.loads(result)
        source_id = source_data.get("sourceId")
        if not source_data.get("success") or not source_id:
            raise RuntimeError(f"Failed to load source: {source_data}")
        total_chars = source_data.get("totalLength", "?")
        print(f"Loaded NEW source: {source_id} ({total_chars} chars)")

    source_bytes = source_file.read_bytes()
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Supply a reviewed UTF-8 text source, with extraction provenance for a PDF") from error
    chunk_ends = load_boundaries(source_text, source_bytes, args.chunk_plan, args.chunk_chars)
    factory = AgentFactory(None, None, model_name, mcp, source_id, project_name,
                           single_agent=args.single_agent, fresh_reading=args.fresh_reading,
                           source_type=args.source_type, projects_dir=projects_dir,
                           source_text=source_text, chunk_ends=chunk_ends)
    factory.temperature = args.temperature
    workers = factory.get_worker_names()
    # The workers-off arm is the paper's "Synthesizer-only" placement: the same
    # Reader, Synthesizer and Translator at the same stops, with no Workers.
    team_size = 0 if args.arm == "synthesizer-only" else min(2, len(workers))
    if args.worker_schedule:
        schedule = json.loads(Path(args.worker_schedule).read_text())
    elif args.resume:
        schedule = json.loads((trace_dir / "run_manifest.json").read_text())["worker_schedule"]
    else:
        chooser = random.Random(args.worker_seed)
        schedule = [chooser.sample(workers, team_size) for _ in chunk_ends]
    if (not isinstance(schedule, list) or len(schedule) != len(chunk_ends) or
            any(not isinstance(row, list) or len(row) != team_size or
                len(set(row)) != len(row) or any(name not in workers for name in row) for row in schedule)):
        raise ValueError("Worker schedule must assign distinct available workers to every fixed passage")
    factory.worker_schedule = schedule
    from swarm.core import _config
    sdk_versions = {name: importlib.metadata.version(name) for name in ("google-genai", "pydantic", "python-dotenv")}
    treatment = "restored-exploratory-teacher+wisdom-2026-10-06+demonstration-2026-10-09"
    provider_record = {"provider": "google-genai", "model": model_name, "temperature": args.temperature,
                       "unspecified_sampling": "provider defaults", "sdk_versions": sdk_versions,
                       "rate_limit_config": _config}
    history = "fresh_agents_per_phase_shared_graph"
    flow = ["Translator receives every cited node with its source passage and revision history; graph tools kept",
            "Synthesizer receives the round's complete contributions as text with disagreement edges marked",
            "Original Teacher thinking prompts restored from bb2db5b with mechanical API compatibility changes",
            "Targeted wisdom corrections retain roles, distinguish inference, include non-attachment and invitation, and allow residual conflict",
            "thinking and translations refuse HTML entities, escaped quotes and title suffixes",
            "Demonstration framing: the prompts no longer call the reading training data; the thoughts are the simulated reader's, written for people to read"]
    manifest = {
        "schema": 1, "project": project_name, "source_id": source_id,
        "source": {"path": str(source_file), "sha256": digest(source_bytes),
                   "provenance": json.loads(Path(args.source_provenance).read_text()) if args.source_provenance else None},
        "treatment": treatment, "flow_changes": flow, "arm": args.arm, "effective_anchor": IDENTITY_MANTRA,
        "source_type": args.source_type, "fresh_reading": args.fresh_reading,
        "history": history, "chunk_ends_utf16": chunk_ends,
        "worker_schedule": schedule, "worker_seed": args.worker_seed,
        **provider_record, "python": sys.version,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "tool": args.tool_identity,
        "runner_git": git_identity(_repo_root), "orchestrator_git": git_identity(_repo_root / "orchestrator"),
        "runner_files": {name: digest((_repo_root / "chronological_metacognition" / name).read_bytes())
                         for name in ("run_reader.py", "reading_state.py")},
        "composed_prompts": factory.prompts(),
        "role_tools": {name: factory._create_mcp_wrapper(name).get_gemini_tools()
                       for name in ["reader", *workers, "synthesizer", "translator"]},
    }
    record = RunRecord(trace_dir, manifest, resume=args.resume)
    factory.record = record
    write_json(trace_dir / "worker_schedule.json", schedule)
    bus = MessageBus(autosave_path=str(trace_dir / "swarm.jsonl"))
    factory.bus = bus
    from google import genai
    client = genai.Client(api_key=api_key)
    factory.client = client
    start_time = datetime.now()
    total_rounds, status, failure = 0, "partial", None
    monitor_task = asyncio.create_task(progress_monitor(mcp, source_id))
    print(f"Model: {model_name}; tool: {args.tool_identity['packages']['understanding-graph']}")
    print(f"Fixed passages: {len(chunk_ends)}; {history.replace('_', ' ')}; worker schedule saved")
    try:
        async def get_progress():
            return await check_progress(mcp, source_id)
        total_rounds = await run_reading_session(factory, bus, get_progress, round_delay=5.0,
                         state_file=trace_dir / "phase_state.json", start_phase=args.start_phase)
        audit = factory.graph_state.validate_all()
        _, final_done = await check_progress(mcp, source_id)
        if not final_done:
            raise RuntimeError("Source is not complete after reflection and translation")
        exported = json.loads(await mcp.call_tool("source_export", {"sourceId": source_id, "thinkingMode": "fluid"}))
        if not exported.get("success"):
            raise RuntimeError(f"Export failed: {exported}")
        (trace_dir / "reading.md").write_text(exported["output"], encoding="utf-8")
        write_json(trace_dir / "artifact_audit.json", audit)
        status = "completed"
        record.event("invocation_completed", rounds=total_rounds, audit=audit)
    except BaseException as error:
        status, failure = "failed", str(error)
        record.event("invocation_failed", error_type=type(error).__name__, message=failure)
        raise
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        try:
            client.close()
        except Exception as error:
            record.event("cleanup_failed", resource="model_client", message=str(error))
        if bus.autosave_file:
            bus.autosave_file.close()
        end_time = datetime.now()
        summary = {"project": project_name, "source_file": str(source_file), "source_id": source_id,
                   "status": status, "error": failure, "total_rounds": total_rounds,
                   "start_time": start_time.isoformat(), "end_time": end_time.isoformat(),
                   "duration_seconds": (end_time - start_time).total_seconds(),
                   "model": model_name, "arm": args.arm,
                   "mode": history, "manifest": "run_manifest.json"}
        write_json(trace_dir / "summary.json", summary)
    print(f"Completed {total_rounds} verified rounds. Reading and audit: {trace_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent reading system that builds understanding graphs. Continues until source is complete.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_reader.py material/metamorphosis.txt
  python run_reader.py paper.txt --source-type paper --project my-paper
  python run_reader.py book.txt --single-agent --source-type fiction
  python run_reader.py novel.txt --fresh-reading  # Ground claims in encountered passages
        """
    )

    parser.add_argument("source", help="Path to UTF-8 source text to read")
    parser.add_argument("--project", "-p", help="Project name (default: source filename)")
    parser.add_argument("--source-type", "-s", default="text",
                        choices=["text", "paper", "fiction", "docs", "code"],
                        help="Type of source material (default: text)")
    parser.add_argument("--single-agent", action="store_true",
                        help="Use single belief_tracker agent instead of full team")
    parser.add_argument("--resume", "-r", action="store_true",
                        help="Resume existing project instead of starting fresh")
    parser.add_argument("--fresh-reading", "-f", action="store_true",
                        help="Read as encountering the work for the first time")
    parser.add_argument("--trace-dir", "-t",
                        help="Directory to save traces (default: .local-work/traces/{project})")
    parser.add_argument("--projects-dir",
                        help="Directory for working graphs (default: .local-work/projects)")
    parser.add_argument("--start-phase",
                        choices=["read", "think", "synthesize", "translate"],
                        help="Start from a specific phase (for resume after crash)")
    parser.add_argument("--ug-cli", default=os.environ.get("UG_CLI"),
                        help="Built Understanding Graph bin/cli.js override, shared with the viewer")
    parser.add_argument("--require-tool-version", default="0.2.1",
                        help="Exact reviewed tool version required for this treatment")
    parser.add_argument("--chunk-chars", type=int, default=2000,
                        help="Target characters for deterministic complete-paragraph stops")
    parser.add_argument("--chunk-plan", help="JSON plan with pinned source hash and contiguous paragraph offsets")
    parser.add_argument("--source-provenance", help="JSON source edition/extraction provenance to retain with the run")
    parser.add_argument("--worker-schedule", help="Saved JSON list of worker pairs, one pair per fixed passage")
    parser.add_argument("--worker-seed", type=int, help="Optional seed for the saved random worker schedule")
    parser.add_argument("--temperature", type=float, default=1.0, help="Recorded Gemini sampling temperature")
    parser.add_argument("--arm", choices=["full", "synthesizer-only"], default="full",
                        help="full: two drawn Workers per stop; synthesizer-only: no Workers (comparison arm)")

    args = parser.parse_args()
    try:
        asyncio.run(run_reader(args))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
