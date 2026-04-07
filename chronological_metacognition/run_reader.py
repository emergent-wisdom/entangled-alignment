#!/usr/bin/env python3
"""
Understanding Graph Reader
--------------------------
Multi-agent reading system that builds understanding graphs from text.
Continues until the source is completely read, auto-restarts if agents stall.

Usage:
    python run_reader.py material/metamorphosis.txt --project metamorphosis
    python run_reader.py material/paper.pdf --project my-paper
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load .env from repo root
_repo_root = Path(__file__).parent.parent
load_dotenv(_repo_root / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "emergent-swarm", "src"))
from swarm import MessageBus, SwarmAgent, MCPClient

# Let agents run until they finish (or hit this limit)
MAX_TURNS = 10000

# Rate limit handling (matches _RATE_LIMIT_COOLDOWN in emergent-swarm/core.py)
RATE_LIMIT_WAIT = 3600  # 1 hour in seconds

async def step_with_rate_limit(agent, agent_name: str = "agent"):
    """Run agent.step() with rate limit handling. Waits 1 hour on 429."""
    while True:
        try:
            await agent.step()
            return
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                print(f"\n⚠️  Rate limit hit for {agent_name}. Waiting {RATE_LIMIT_WAIT // 60} minutes...")
                await asyncio.sleep(RATE_LIMIT_WAIT)
                print(f"  Resuming {agent_name}...")
            else:
                raise

# ============================================================================
# PROMPT LOADING
# ============================================================================

# Cache for loaded prompts
_prompt_cache = {}

def get_prompts_dir() -> Path:
    """Get the prompts directory path."""
    script_dir = Path(__file__).parent
    return (script_dir / "../understanding-graph/prompts").resolve()

def load_prompt(path: str) -> str:
    """Load a prompt file from understanding/prompts/."""
    if path in _prompt_cache:
        return _prompt_cache[path]

    full_path = get_prompts_dir() / path
    try:
        content = full_path.read_text(encoding="utf-8")
        _prompt_cache[path] = content
        return content
    except FileNotFoundError:
        print(f"Warning: prompts/{path} not found")
        return ""

def compose_prompt(*paths: str) -> str:
    """Compose a prompt from multiple files."""
    parts = [load_prompt(p) for p in paths]
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
EMERGENT_WISDOM = load_prompt("core/emergent_wisdom.md")

TEAMMATES = """
## HOW THIS WORKS
You work in PHASES. Each phase has different agents.
Your work goes into the GRAPH - other agents read from it directly.
When you finish your work, just stop. The orchestrator handles phase transitions.
"""

# Graph Vision - tools for "seeing" the graph
# graph_context_region allows drilling into regions when graph is large (>50 nodes)
GRAPH_VISION_TOOLS = ["graph_skeleton", "graph_context", "graph_context_region", "graph_semantic_search", "graph_find_by_trigger"]

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
When calling graph tools, pass `project: "{project_name}"`.
When calling `source_position`, pass `sourceId: "{source_id}"`.

## YOUR TASK
Read what exists in the graph. For each node, ask: **what's the other perspective?**
Add nodes that challenge, refine, or counter existing views. Debate through the graph.

## ENRICH, DON'T DUPLICATE (OR SKIP)
Before adding anything, STUDY what already exists this round:
1. Check `graph_updates()` to see commits and nodes added recently
2. Use `graph_semantic_search` to find similar insights

Then decide:
- **If you have a UNIQUE perspective** → Add it as a new node
- **If you have a NEIGHBORING thought or DIFFERENT angle** → Add it, but REFERENCE the existing thought. Show you are aware of it. Connect with an edge explaining the relationship.
- **OLDER node exists (from previous rounds)** → RESPECT it. Create a NEW node that REFERENCES the old one, showing belief evolution. Do NOT rewrite old nodes - they represent what was believed *at that time*. Use edges like `refines`, `supersedes`, or `validates` to show the temporal link.
- **If your thought is IDENTICAL to what exists** → SKIP YOUR TURN. Say "Nothing unique to add."

It is BETTER to skip than to create redundant nodes. But neighboring thoughts that acknowledge and reference existing ones are valuable.

## WEAVE THOUGHTS INTO THE DOCUMENT
When you read a document node and it inspires a thought, create an edge FROM it TO your new node.
This marks understanding or thought generation from that text. We know from which part of the reading each thought originates.
This represents the messy entanglement of understanding - we see how thoughts emerge from text as you read.

Content nodes have trigger "foundation" and names like "Content 2%", "Content 4%".

**CRITICAL: You MUST connect your new node to the graph.**
Use `graph_batch` to create the concept AND connect it in one atomic operation.

```javascript
graph_batch({{
  operations: [
    {{ tool: "graph_add_concept", params: {{
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

## IDENTITY MANTRA (RECITE EXACTLY - THIS IS TRAINING DATA)
{IDENTITY_MANTRA}

**SACRED**: Copy exactly. **THE PHYSICS**: Use the mantra as a Prism to refract the text. Your thought must be a descendant of these values.

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
**ALWAYS** pass `project: "{project_name}"` to every tool call.

{graph_vision}

{api_reference}

## YOUR ROLE
You have unique analysis tools. Use them to find and fix structural problems:
- Missing node types (no models? no questions? no predictions? no tensions?)
- Disconnected clusters that should be linked
- Semantic gaps between related concepts

## WORKFLOW

1. **DIAGNOSE**: Call `graph_thermostat(project="{project_name}")`
   - **FROZEN**: Graph is too homogeneous. Add diverse node types.
   - **OVERHEATED**: Graph is too fragmented. Add connecting edges.
   - **LIQUID**: Graph is healthy. Check for specific gaps.

2. **FIND GAPS**: Call `graph_analyze(project="{project_name}")` and `graph_semantic_gaps(project="{project_name}")`

3. **FIX**: Use `graph_batch` to add missing nodes or `graph_connect` to bridge gaps.

Example - adding a missing question:
```javascript
graph_batch({{
  operations: [
    {{ tool: "graph_add_concept", params: {{
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
Pass `project: "{project_name}"` to all graph tools.

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
**ALWAYS** pass `project: "{project_name}"` to every tool call.
If you use the default project, you will see an empty graph.

## IDENTITY MANTRA (RECITE EXACTLY - THIS IS TRAINING DATA)
{IDENTITY_MANTRA}

**SACRED**: Copy exactly. **THE PHYSICS**: Use the mantra as a Prism to refract the text. Your thought must be a descendant of these values.

{philosophy}

{EMERGENT_WISDOM}

{synthesizer_role}

{graph_vision}

{api_reference}

## HOW THIS WORKS
You work in PHASES. Before you:
- The READER created content chunks (trigger: "chunk")
- Workers (connector, skeptic, belief_tracker, axiologist, psychologist) created concept nodes

All their work is in the GRAPH. You DISCOVER by reading it.
Use graph_updates() and graph_find_by_trigger() to see what was created this round.
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
**ALWAYS** pass `project: "{project_name}"` to tool calls.

{philosophy}

{EMERGENT_WISDOM}

{graph_vision}

## YOUR MISSION
Make each thought SELF-CONTAINED. When a thinking node references `n_abc123 (Some Concept)`, you must SPELL OUT that concept's full understanding - don't summarize, don't abbreviate. The reader should understand everything without looking anything up.

{translator_role}

## WORKFLOW
1. Find thinking nodes: `graph_find_by_trigger({{ trigger: "thinking", missingMetadata: "translated" }})`
2. For each thinking node:
   a. **READ** the prose - it has node IDs like `n_abc123 (Name)`
   b. **LOOK UP** each referenced node - get its FULL `understanding` field
   c. **UNPACK** - replace each reference with the full content, woven naturally into the thought. Don't summarize - spell it out in all its complexity.
   d. **SAVE** to metadata field `thought_fluid`

The output should be LONGER than the input - you're expanding references into full explanations.

## THE BIGGER PICTURE
You are leveraging the Understanding Graph and the diverse set of thoughts within it to achieve a higher degree of metacognition, intelligence, and wisdom. This scaffolding makes AI more like human - you are creating the synthetic training data for future generations.

## RESOLVED PREDICTIONS ARE GOLD
You are a DETECTIVE OF YOUR OWN COGNITION - figuring out why you thought and think certain ways.

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
# TOOL ACCESS CONTROL
# ============================================================================
class RestrictedMCP:
    """Wraps MCP client to restrict tools and inject agent identity."""
    def __init__(self, mcp_client, allowed_tools=None, banned_tools=None, agent_name=None):
        self.real_mcp = mcp_client
        self.allowed = set(allowed_tools) if allowed_tools else None
        self.banned = set(banned_tools) if banned_tools else set()
        self.agent_name = agent_name
        # Copy tools attribute for compatibility
        self.tools = mcp_client.tools

    def get_gemini_tools(self):
        tools = self.real_mcp.get_gemini_tools()
        filtered = []
        for t in tools:
            name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
            if self.allowed and name not in self.allowed:
                continue
            if self.banned and name in self.banned:
                continue
            filtered.append(t)
        return filtered

    async def call_tool(self, name, args):
        if self.allowed and name not in self.allowed:
            return f"Error: You are not authorized to use tool '{name}'."
        if self.banned and name in self.banned:
            return f"Error: You are not authorized to use tool '{name}'."

        # Auto-inject agent_name into graph_batch and graph_add_concept calls
        if name in ("graph_batch", "graph_add_concept") and self.agent_name:
            if isinstance(args, dict):
                args["agent_name"] = self.agent_name

        return await self.real_mcp.call_tool(name, args)


# ============================================================================
# AGENT FACTORY (creates fresh agents on demand)
# ============================================================================

class AgentFactory:
    """Creates fresh agents on demand with proper tool restrictions."""

    def __init__(self, bus, client, model_name, mcp, source_id, project_name, single_agent=False, fresh_reading=False, source_type="text"):
        self.bus = bus
        self.client = client
        self.model_name = model_name
        self.mcp = mcp
        self.source_id = source_id
        self.project_name = project_name
        self.single_agent = single_agent
        self.fresh_reading = fresh_reading
        self.source_type = source_type

    def _create_mcp_wrapper(self, agent_name: str) -> RestrictedMCP:
        """Create per-agent MCP wrapper with strict tool restrictions by role."""

        # Reader: Only source tools + vision (no graph writing)
        if agent_name == "reader":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=["source_read", "source_position"] + GRAPH_VISION_TOOLS,
                agent_name=agent_name
            )

        # Curator: Vision + analysis + graph_batch (can fix gaps it finds)
        elif agent_name == "curator":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["graph_thermostat", "graph_analyze", "graph_score", "graph_semantic_gaps", "graph_batch", "graph_connect"],
                agent_name=agent_name
            )

        # Synthesizer: Vision + doc_append_thinking + graph_batch (no source reading, no doc_insert_thinking)
        elif agent_name == "synthesizer":
            return RestrictedMCP(
                self.mcp,
                banned_tools=["source_read", "doc_revise", "doc_insert_thinking"],
                agent_name=agent_name
            )

        # Translator: Vision + doc_revise + metadata only (no graph writing)
        elif agent_name == "translator":
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["doc_revise", "translate_thinking"],
                agent_name=agent_name
            )

        # Workers: Vision (graph + source) + graph_batch for writing
        else:
            return RestrictedMCP(
                self.mcp,
                allowed_tools=GRAPH_VISION_TOOLS + ["source_position"] + ["graph_batch"],
                agent_name=agent_name
            )

    def create(self, name: str) -> SwarmAgent:
        """Create a fresh agent by name."""
        prompts = {
            "reader": make_reader_prompt(self.source_id, self.project_name),
            **{wname: make_worker_prompt(wname, self.project_name, self.source_id) for wname in WORKER_ROLES},
            "curator": make_curator_prompt(self.project_name),
            "synthesizer": make_synthesizer_prompt(self.project_name, self.source_id),
            "translator": make_translator_prompt(self.project_name),
        }

        prompt = prompts[name]

        # Inject fresh reading mode for all agents
        if self.fresh_reading:
            fresh_reading_prompt = load_prompt("modes/fresh_reading.md")
            prompt = fresh_reading_prompt + "\n\n" + prompt

        # Each agent gets its own MCP wrapper with identity injection
        agent_mcp = self._create_mcp_wrapper(name)

        agent = SwarmAgent(
            name=name,
            system_instructions=prompt,
            bus=self.bus,
            client=self.client,
            model_name=self.model_name,
            extra_tools=[agent_mcp],
        )
        return agent

    def get_recent_commits(self, limit=10, after_id=None):
        """Query recent commits directly from SQLite."""
        import sqlite3
        import json
        db_path = Path(__file__).parent.parent / "projects" / self.project_name / "store.db"
        if not db_path.exists():
            return []
        try:
            conn = sqlite3.connect(db_path)
            if after_id:
                rows = conn.execute(
                    "SELECT id, message, agent_name, node_ids FROM commits WHERE id > ? ORDER BY created_at DESC LIMIT ?",
                    (after_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, message, agent_name, node_ids FROM commits ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            conn.close()
            return [{"id": r[0], "message": r[1], "agent": r[2], "node_ids": json.loads(r[3]) if r[3] else []} for r in rows]
        except Exception:
            return []

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
    """Track which phase we're in for resume capability."""
    PHASES = ["read", "think", "synthesize", "translate"]

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.round = 0
        self.phase = "read"
        self.load()

    def load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.round = data.get("round", 0)
                self.phase = data.get("phase", "read")
                print(f"  Resuming from round {self.round}, phase: {self.phase}")
            except:
                pass

    def save(self, round_num: int, phase: str):
        self.round = round_num
        self.phase = phase
        self.state_file.write_text(json.dumps({
            "round": round_num,
            "phase": phase,
            "timestamp": datetime.now().isoformat()
        }))

    def clear(self):
        if self.state_file.exists():
            self.state_file.unlink()
        self.round = 0
        self.phase = "read"

    def should_skip(self, round_num: int, phase: str) -> bool:
        """Check if we should skip this phase (already completed in a previous run)."""
        if round_num < self.round:
            return True
        if round_num == self.round:
            my_idx = self.PHASES.index(phase) if phase in self.PHASES else 0
            saved_idx = self.PHASES.index(self.phase) if self.phase in self.PHASES else 0
            return my_idx < saved_idx
        return False


# ============================================================================
# LOCAL ORCHESTRATOR (creates fresh agents each round)
# ============================================================================

async def run_reading_session(
    factory: AgentFactory,
    bus,
    get_progress,
    round_delay: float = 5.0,
    cooldown: float = 2.0,
    state_file: Path = None,
    start_phase: str = None,
):
    """
    Local orchestrator for the multi-agent reading system.
    Creates FRESH agents each round - no accumulated state.

    Phases:
    1. read - Reader reads chunks
    2. think - Workers create concept nodes
    3. synthesize - Synthesizer creates thinking nodes
    4. translate - Translator converts to fluid prose
    """
    tracker = PhaseTracker(state_file) if state_file else None

    # Handle explicit start phase override
    if start_phase and tracker:
        tracker.phase = start_phase
        tracker.round = tracker.round or 1
        print(f"  Overriding start phase to: {start_phase}")

    # Start from saved round when resuming, otherwise 0
    round_count = (tracker.round - 1) if tracker and tracker.round > 1 else 0
    workers = factory.get_worker_names()

    while True:
        round_count += 1
        progress, done = await get_progress()

        if done or progress >= 100:
            print(f"\n✅ Reading complete at {progress}%")
            if tracker:
                tracker.clear()
            break

        print(f"\n--- Round {round_count} ({progress}%) ---")

        # ===== PHASE: READ =====
        if not (tracker and tracker.should_skip(round_count, "read")):
            print("  [Phase: READ]")
            reader = factory.create("reader")
            reader.kickstart("First, check graph_find_by_trigger({ trigger: 'thinking', limit: 3 }) to see recent thoughts. Read their content with graph_context. Then read until the next THOUGHT MOMENT - an emotional peak, tension point, or shift that deserves reflection. STOP there. Quality over quantity.")
            await step_with_rate_limit(reader, "reader")
            reader.close()
            await asyncio.sleep(round_delay)
            if tracker:
                tracker.save(round_count, "think")
        else:
            print("  [Phase: READ] (skipped)")

        # ===== PHASE: THINK (2 random workers per round) =====
        if not (tracker and tracker.should_skip(round_count, "think")):
            import random
            selected_workers = random.sample(workers, min(2, len(workers)))
            print(f"  [Phase: THINK] - workers: {' → '.join(selected_workers)}")

            # Get baseline commit ID after reader
            baseline_commits = factory.get_recent_commits(limit=1)
            baseline_id = baseline_commits[0]["id"] if baseline_commits else None

            for i, name in enumerate(selected_workers):
                print(f"    > {name} ({i+1}/{len(selected_workers)})")
                agent = factory.create(name)

                # Get commits since baseline (what reader + previous workers added)
                recent = factory.get_recent_commits(limit=10, after_id=baseline_id) if baseline_id else factory.get_recent_commits(limit=5)

                if recent:
                    commit_summary = "\n".join([f"- {c['agent']}: {c['message']} (nodes: {', '.join(c['node_ids'][:3])})" for c in recent[:5]])
                    kickstart = f"Recent commits this round:\n{commit_summary}\n\nOffer diverse_from perspectives on these nodes."
                else:
                    kickstart = "You're first. Add your perspective on the new content."

                agent.kickstart(kickstart)
                await step_with_rate_limit(agent, name)
                agent.close()
                await asyncio.sleep(round_delay)

            if tracker:
                tracker.save(round_count, "synthesize")
        else:
            print("  [Phase: THINK] (skipped)")

        # ===== PHASE: SYNTHESIZE =====
        if not (tracker and tracker.should_skip(round_count, "synthesize")):
            print("  [Phase: SYNTHESIZE]")
            synthesizer = factory.create("synthesizer")
            synthesizer.kickstart("Create thinking nodes that synthesize the new concept nodes.")
            await step_with_rate_limit(synthesizer, "synthesizer")
            synthesizer.close()
            if tracker:
                tracker.save(round_count, "translate")
        else:
            print("  [Phase: SYNTHESIZE] (skipped)")

        # ===== PHASE: TRANSLATE =====
        if not (tracker and tracker.should_skip(round_count, "translate")):
            print("  [Phase: TRANSLATE]")
            translator = factory.create("translator")
            translator.kickstart("Translate new thinking nodes to fluid prose.")
            await step_with_rate_limit(translator, "translator")
            translator.close()
        else:
            print("  [Phase: TRANSLATE] (skipped)")

        # Mark round complete
        if tracker:
            tracker.save(round_count + 1, "read")

    return round_count


# ============================================================================
# MAIN
# ============================================================================

async def check_progress(mcp, source_id):
    """Check reading progress, returns (percent, done)."""
    try:
        result = await mcp.call_tool("source_position", {"sourceId": source_id})
        data = json.loads(result)
        if data.get("success"):
            return data.get("percent", 0), data.get("done", False)
    except:
        pass
    return 0, False


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

        if done or progress >= 100:
            break


async def run_reader(args):
    """Run the multi-agent reader until source is completely read."""
    source_file = Path(args.source).resolve()
    if not source_file.exists():
        print(f"Error: {source_file} not found")
        return

    # All paths relative to script location (not cwd)
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent  # entangled-alignment root

    project_name = args.project or source_file.stem

    # Graph data lives in projects/ at repo root (where web frontend reads from)
    projects_dir = repo_root / "projects"
    project_path = projects_dir / project_name

    # Check for existing project data
    if project_path.exists() and not args.resume:
        print(f"\n⚠️  ERROR: Project '{project_name}' already exists at {project_path}")
        print(f"   Use --resume to continue, or delete it manually:")
        print(f"   rm -rf {project_path}")
        print()
        return

    # Setup trace directory
    if args.trace_dir:
        trace_dir = Path(args.trace_dir)
    else:
        trace_dir = script_dir / "traces" / project_name
    trace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Traces: {trace_dir}")
    print(f"Graph:  {project_path}")

    # Start MCP (server from understanding-graph submodule)
    mcp_server = repo_root / "understanding-graph" / "packages" / "mcp-server" / "dist" / "index.js"
    mcp = MCPClient(
        command="node",
        args=[str(mcp_server)],
        cwd=str(repo_root),
        name="understanding",
        env={"PROJECT_DIR": str(projects_dir), "TOOL_MODE": "reading"}
    )
    await mcp.start()
    print(f"Connected to MCP ({len(mcp.tools)} tools)")

    # --- SAFETY PATCH: HIDE ATOMIC MUTATORS ---
    # Forces agents to use graph_batch (which enforces orphan checks).
    EXCLUDED_TOOLS = {
        "graph_add_concept",
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
        "type": "chronological_reading",
        "sourceTitle": source_file.stem
    })

    # Check for existing source to resume
    existing_sources = await mcp.call_tool("source_list", {})
    existing_data = json.loads(existing_sources)
    sources = existing_data.get("sources", [])

    # Find a source with matching title that isn't complete
    resumable = [s for s in sources if s.get("title") == source_file.stem and s.get("status") != "completed"]

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
        total_chars = source_data.get("totalLength", "?")
        print(f"Loaded NEW source: {source_id} ({total_chars} chars)")

    # Create message bus with trace logging
    bus = MessageBus(autosave_path=str(trace_dir / "swarm.jsonl"))

    # Setup LLM client
    api_key = os.environ.get("GOOGLE_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL")
    if not model_name:
        print("Error: GEMINI_MODEL not set in environment")
        await mcp.close()
        return
    if not api_key:
        print("Error: GOOGLE_API_KEY not found")
        await mcp.close()
        return

    print(f"Using model: {model_name}")
    # Rate limiting handled by core.py _global_throttle (5s between API calls)
    from google import genai
    client = genai.Client(api_key=api_key)

    # Create agent factory (agents created fresh each round)
    print("\n" + "="*60)
    print("AGENT FACTORY READY")
    print("="*60)

    factory = AgentFactory(
        bus=bus,
        client=client,
        model_name=model_name,
        mcp=mcp,
        source_id=source_id,
        project_name=project_name,
        single_agent=args.single_agent,
        fresh_reading=args.fresh_reading,
        source_type=args.source_type,
    )

    # Print the active mode for clarity
    active_mode = SOURCE_TYPE_MAP.get(args.source_type, "narrative")
    print(f"  Mode: {active_mode.upper()}")

    workers = factory.get_worker_names()
    print(f"  Workers: {', '.join(workers)}")
    print(f"  Phases: reader → workers (2 random) → synthesizer → translator")
    print(f"  Mode: Fresh agents each round (no accumulated state)")
    if args.fresh_reading:
        print(f"  🌱 FRESH READING MODE: Agents pretend no prior knowledge of text")

    print("\n" + "="*60)
    print("STARTING READING SESSION")
    print("="*60)

    start_time = datetime.now()

    # Start progress monitor in background
    monitor_task = asyncio.create_task(
        progress_monitor(mcp, source_id)
    )

    try:
        # Progress callback
        async def get_progress():
            return await check_progress(mcp, source_id)

        # Run local reading session orchestrator
        total_rounds = await run_reading_session(
            factory, bus,
            get_progress=get_progress,
            round_delay=5.0,  # 5s between phases
            cooldown=2.0,  # 2s between agent steps
            state_file=trace_dir / "phase_state.json",
            start_phase=args.start_phase
        )
        print(f"\n✅ Agents finished after {total_rounds} rounds")

    except KeyboardInterrupt:
        print("\n⏸️  Interrupted by user")
        total_rounds = 0
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Close Gemini client to prevent 429s
        if 'client' in locals() and hasattr(client, "close"):
            try:
                client.close()
                print("[CLEANUP] Gemini client closed.")
            except:
                pass

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Final progress check
    final_progress, _ = await check_progress(mcp, source_id)

    # Save summary
    all_agents = ["reader"] + factory.get_worker_names() + ["synthesizer", "translator"]
    summary = {
        "project": project_name,
        "source_file": str(source_file),
        "source_id": source_id,
        "status": "completed" if final_progress >= 100 else "partial",
        "final_progress_percent": final_progress,
        "total_rounds": total_rounds,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "model": model_name,
        "agents": all_agents,
        "mode": "fresh_agents_per_round",
        "fresh_reading": args.fresh_reading,
    }

    with open(trace_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Analyze results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Progress: {final_progress}%")
    print(f"Total turns: {total_rounds}")
    print(f"Duration: {duration:.1f}s ({duration/60:.1f}m)")

    result = await mcp.call_tool("graph_skeleton", {})
    print("\nGRAPH SKELETON:")
    print(result[:2000] if result else "No skeleton")

    result = await mcp.call_tool("graph_score", {})
    print(f"\nGRAPH SCORE: {result}")

    await mcp.close()

    print(f"\nTraces saved to: {trace_dir}")
    print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent reading system that builds understanding graphs. Continues until source is complete.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_reader.py material/metamorphosis.txt
  python run_reader.py material/paper.pdf --project my-paper
  python run_reader.py book.txt --single-agent --source-type fiction
  python run_reader.py novel.txt --fresh-reading  # Agents pretend no prior knowledge
        """
    )

    parser.add_argument("source", help="Path to source file to read")
    parser.add_argument("--project", "-p", help="Project name (default: source filename)")
    parser.add_argument("--source-type", "-s", default="text",
                        choices=["text", "paper", "fiction", "docs", "code"],
                        help="Type of source material (default: text)")
    parser.add_argument("--single-agent", action="store_true",
                        help="Use single belief_tracker agent instead of full team")
    parser.add_argument("--resume", "-r", action="store_true",
                        help="Resume existing project instead of starting fresh")
    parser.add_argument("--fresh-reading", "-f", action="store_true",
                        help="Fresh reading mode: agents pretend no prior knowledge of text")
    parser.add_argument("--trace-dir", "-t",
                        help="Directory to save traces (default: traces/{project}/{timestamp})")
    parser.add_argument("--start-phase",
                        choices=["read", "think", "synthesize", "translate"],
                        help="Start from a specific phase (for resume after crash)")

    args = parser.parse_args()
    asyncio.run(run_reader(args))


if __name__ == "__main__":
    main()
