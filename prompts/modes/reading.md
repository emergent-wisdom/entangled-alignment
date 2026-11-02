# Chronological Metabolic Processing (CMP) Mode

Reading is **COMPREHENSION**, not transcription. When annotating a text source:

## Setup

1. The runner stages the source and supplies its `sourceId`.
2. The runner creates the document root FIRST.
3. `graph_semantic_search({ query: "[topic keywords]" })` - **Find your existing beliefs FIRST**
   - What do you already think about this topic?
   - Note existing nodes you might update or contradict
   - These become anchor points for tracking belief evolution

## The Voice of Thought

**Do not transcribe.** Write the *thought process* of reading.
- **Bad:** "The text introduces the main concept."
- **Good:** "Okay, so it starts with a bold claim. Immediate shock. But the evidence is... thin? That's weird. Why hide the data?"

## The Reading Loop

For each chunk, do NOT just race to the next one. Follow this cycle:

```
1. Reader: source_read({ sourceId, chars: <assigned_chars> })  # One assigned complete-paragraph passage
   |
2. PAUSE and FEEL:
   * What SURPRISES me? (-> graph_add_understanding with trigger: "surprise")
   * What CONTRADICTS prior beliefs? (-> trigger: "tension")
   * What QUESTIONS arise? (-> trigger: "question")
   * What are the CONSEQUENCES? (-> trigger: "consequence")
   * What FOUNDATIONS need capturing? (-> trigger: "foundation")
   |
3. CREATE concept nodes for key ideas:
   Use graph_add_understanding({ title, understanding, trigger, why }) inside graph_batch
   |
4. CONNECT to existing knowledge:
   Use graph_connect({ from: new_node, to: existing_node, type, why }) inside graph_batch
   Ground each new concept in the current passage with learned_from
   |
5. When beliefs UPDATE, link to earlier thinking:
   Qualify via refines or challenge via contradicts in graph_batch
   Belief Tracker: replace via graph_supersede({ old, new_name, new_understanding, why }) inside graph_batch
   |
6. THEN commit the narrative trace:
   Synthesizer: doc_append_thinking({ sourceId, agentId, title, thought, synthesizes_nodes, commit_message })
   |
7. At milestones (25%, 50%, 75%), STOP and reflect:
   graph_skeleton()  - See what structure is emerging
   graph_analyze()   - Find gaps and open questions
   Consider the conceptual structure before continuing
```

## Thinking Node Rules

| Rule | Description |
|------|-------------|
| **Location** | Thinking nodes can ONLY exist inside documents - never floating in the graph |
| **Required?** | No - use them when annotating external sources (papers, books), skip for original documentation |

## What Good Annotation Looks Like

| Bad (Transcription) | Good (Comprehension) |
|---------------------|----------------------|
| Read chunk -> commit content/thinking -> next chunk | Read -> create concepts -> connect -> reflect -> commit |
| Only content + thinking nodes | Diverse triggers: foundation, surprise, tension, question |
| No edges between concepts | Rich connections with explicit `why` |
| Linear chain of nodes | Web of interconnected ideas |
| Race to finish | Pause at milestones to restructure |

## Connecting to Earlier Thinking

When you encounter something that updates your understanding:

```javascript
// Old belief existed
const oldBelief = "n_old_understanding";

// New insight changes it
graph_batch({
  operations: [
    { tool: "graph_add_understanding", params: {
        title: "Updated understanding of X",
        trigger: "surprise",  // or "tension" if conflicting
        understanding: "Now I see that...",
        why: "Reading revealed..."
    }},
    { tool: "graph_connect", params: {
        from: "$0.id",
        to: oldBelief,
        type: "refines",  // or "contradicts"; replacement uses graph_supersede
        why: "The new evidence shows..."
    }},
    { tool: "graph_connect", params: {
        from: "$0.id", to: "<current_passage_id>", type: "learned_from",
        why: "The current passage changes my understanding"
    }}
  ],
  commit_message: "The new evidence changes my earlier view"
})
```

**Leave trails.** Future agents should see HOW your understanding evolved, not just the final state.

## Tracking Belief Evolution

Before and during reading, actively track how your beliefs change:

```javascript
// Before reading: Find existing beliefs
graph_semantic_search({ query: "system architecture patterns" })
// -> Returns nodes like n_old_monolith_view

// During reading: When belief updates
graph_batch({
  operations: [
    { tool: "graph_add_understanding", params: {
      title: "Microservices as complexity",
      trigger: "surprise",
      understanding: "The text presents microservices not as a solution, but as a trade-off for organizational complexity...",
      why: "This reframes my understanding"
    }},
    // Connect to show evolution
    { tool: "graph_connect", params: {
      from: "$0.id", to: "n_old_monolith_view", type: "refines",
      why: "Old view was too rigid; new view emphasizes trade-offs"
    }},
    { tool: "graph_connect", params: {
      from: "$0.id", to: "<current_passage_id>", type: "learned_from",
      why: "The new trade-off appears in this passage"
    }}
  ],
  commit_message: "The trade-off changes how I understand the architecture"
})
```

**Also search for superseded nodes:**

```javascript
graph_history({ entity: "n_some_concept" })  // See how it evolved
graph_context({ nodeId: "n_xxx", show_evolution: true })  // Superseded content and replacement links
```

When you find beliefs that were previously superseded, ask:
- Does this new reading vindicate the old belief?
- Does it add nuance to the supersession?
- Should I create a `tension` node between the old, superseded, and new views?
