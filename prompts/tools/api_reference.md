# Reading Pipeline API Reference

Follow the live tool schema. Pass `project` only when that schema declares it; the runner selects the project. These instructions describe the verified rc.2 reading workflow, whose operation restrictions are narrower than the general server's capabilities.

## Allowed Batch Operations

Ordinary workers and the Curator may use `graph_add_understanding`, `graph_question`, `graph_connect` and `graph_answer` inside `graph_batch`. The Belief Tracker additionally has `graph_supersede` and a restricted `graph_revise`. Availability in a general tool description does not grant permission to use other operations.

The Synthesizer creates reserved thinking blocks only with `doc_append_thinking`. The Translator saves fluid prose only with `translate_thinking`. Workers do not edit source passages, thinking blocks, translation metadata, document structure or other existing nodes.

## Batch Envelope

```javascript
// CORRECT
graph_batch({
  operations: [
    { tool: "graph_add_understanding", params: { ... } },
    { tool: "graph_connect", params: { ... } }
  ],
  commit_message: "Your reflection on what you're adding and why"
})

// WRONG - fails with "Tool not found"
graph_add_understanding({ ... })
```

Atomic operations are not direct top-level calls. Use `operations`, `tool` and `params`, not an array of `op` objects. `commit_message` is required. `$0.id` refers to the first operation's returned node ID; `$1.id` refers to the second. Substitute fetched IDs for the invented example placeholders.

## Fields

| Operation | Fields |
| --- | --- |
| `graph_add_understanding` | Required `title`, `trigger`, `understanding`, `why` |
| `graph_question` | Required `question`, `speculation`, `why` |
| `graph_connect` | Required `from`, `to`, `type`, `why`; optional descriptive `relation` |
| `graph_answer` | Required exact question ID in `question`, `answer`, `explanation` |
| `graph_supersede` | Required exact earlier concept ID in `old`, `new_name`, `new_understanding`, `why` |
| `graph_revise` | Required exact own current-round ID in `node`, `why`; use `understanding` for the corrected wording |

A `reference` concept additionally requires valid `references`. Use only fields declared by the operation's live schema. Prefer exact IDs over fuzzy names.

### Grounding

Give each understanding its own node, and in the same batch connect it to the exact passage it came from with a **new node → exact passage** `learned_from` edge.

### Revision and Replacement

Changes of meaning belong in new nodes that reference the earlier reading and the passage that changed it.

`graph_supersede` creates **new → old** `supersedes` and archives old. It is for genuine replacement of an ordinary concept, not qualification, questions or prediction resolution. Use the returned new ID to add current-passage grounding in the same batch. Do not use `graph_connect` to create a `supersedes` edge.

`graph_revise` is only for a wording correction to the Belief Tracker's own ordinary concept created this round, confirmed from recorded IDs. A correction that could change meaning requires a new node. No source or thinking block can be revised. Server suggestions to revise a duplicate do not override this protocol.

Use `refines` for qualification, `diverse_from` for competing readings, and outcome → prediction `validates` or `invalidates` for resolution. Retain the earlier nodes in those cases.

## Dedicated Synthetic Tools

`doc_append_thinking` requires `sourceId`, `thought`, `title`, `agentId`, a nonempty `synthesizes_nodes` array, and `commit_message`. Use the actual source ID and exact existing ordinary-concept or directly cited current-passage IDs. A thinking block can cite a current passage directly when workers skip.

`translate_thinking` requires the exact `thinking_node_id`, `thought_fluid` and `commit_message`. Both raw and fluid prose begin with the complete Core and continue with a substantive thought. The fluid version contains no node IDs. These are dedicated top-level tools, not worker batch operations.

## Supported Vocabulary

Ordinary triggers:
`foundation`, `surprise`, `repetition`, `consequence`, `tension`, `question`, `serendipity`, `decision`, `experiment`, `analysis`, `randomness`, `reference`, `library`, `prediction`, `hypothesis`, `model`, `evaluation`.

`thinking` is reserved for synthetic blocks and is not an ordinary concept trigger. `chunk`, `revision`, `insight`, `supersession`, `validation`, `refutation`, `trauma` and `emotion` are not triggers.

Worker semantic edge types:
`relates`, `expresses`, `contradicts`, `diverse_from`, `refines`, `answers`, `questions`, `implements`, `abstracts_from`, `contextualizes`, `inspired_by`, `learned_from`, `validates`, `invalidates`.

`contains` and `next` are document structure; workers do not change them. `supersedes` belongs to the dedicated lifecycle operation. Terms such as `motivates`, `masks`, `could_cause`, `supports` or `alternatives` are not edge types; where useful, state a specific relationship in the optional `relation` field under a supported `type` and explain the evidence in `why`.

### Commit Messages: The Metacognitive Stream

Your commit messages are visible to other agents via `graph_history`. They see not just WHAT you created, but WHY you created it and what you were thinking.

**Descriptive (BAD):**
- "Added tension node about conflict"
- "Connected X to Y"
- "Created prediction about outcome"

**Reflective (GOOD):**
- "Something doesn't add up here - the protagonist's calm feels forced"
- "I'm sensing a pattern: every mention of 'safety' precedes a failure"
- "This contradicts my earlier belief - updating my mental model"
- "The skeptic in me can't let this optimism pass unchallenged"

Your commit message should capture:
- What triggered this thought NOW (not just "I analyzed X")
- Your emotional/cognitive state ("I'm suspicious", "This confirms my hunch")
- How this connects to your evolving understanding

The Synthesizer will read your commits to weave the *debate* between agents, not just the facts.


After a tool refusal, inspect the error and correct the call within your role's permissions. A skipped worker turn ends with `[SKIP]`; an unpersisted required synthesis or translation is not a completed phase.
