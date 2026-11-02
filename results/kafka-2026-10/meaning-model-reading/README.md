# Meaning Model reading

On 1 November 2026, GPT-6.1 Sol at high reasoning effort read the Johnston text using the Meaning Model as its thinking tool, at the code released as version 0.18.1, with its storytelling add-on and the [reading mode](../../../reading-mode/). The reading mode was the Reader's only way to the text. The Reader took the 99 paragraphs in 40 reads of its own choosing and wrote 45 reflections at 41 pauses, the last after the book had ended, each with a prose translation. Two Worker perspectives were named for each stretch of about 4,000 characters, in an order shuffled with seed 20261009.

The reading took two conversations. The first read the whole book, but after paragraph 70 of 99 its record grew thin. The record was cut at that point, at graph revision 162, using the tool's own export, and rebuilt in a fresh store. A second conversation with the same instructions recovered the model and its notes from the store and read on. Paragraphs 1–70 therefore come from the first conversation and paragraphs 71–99 from the second. In both conversations the Reader wrote its period Cuts in bursts, and in the second it held the last burst until the text had ended: the last fifth of the story's text (paragraphs 72–98) is recorded thinly while it is read and filled in afterwards.

The turns whose output is in the store used 47.8M input tokens: 27.5M from the first conversation up to the cut and 20.2M from the second.

## Files

- `store.sqlite` is the exact final SQLite store, with 313 successive versions of the model and 266 graph revisions. No data was removed from it. The model is `metamorphosis-first-reading` and the graph `metamorphosis-encountered-reading`.
- `reflections.md` gives every reflection and its translation in order, each beginning with the Core as recorded.
- `reads.json` records each read: the paragraphs it covered (counted from 0, end exclusive), what the Reader asked for, the Workers it named and when it happened. It also records the sessions and the cut. Only local file paths were removed.
- `prompts/` holds the instructions as the model received them: `AGENTS.md`, `first-prompt.md` (the first message as sent) and `continue-from-cut.md` (the second conversation's first message was that prompt followed by this).
- `run-settings.json` records the model, effort, tool and parameters. It describes the run and is not an executable launcher.

The runtime also passed the operator's general agent instructions to the model, ahead of these: see [`operator-agent-instructions.md`](../operator-agent-instructions.md).

The role prompts in `AGENTS.md` were reused unedited. They speak of a "run owner" that checks the Core, the phases and the references, and that will reject a thought without the Core. No such program ran in this reading: neither the Meaning Model nor the reading mode checks the recital. All 45 reflections and translations open with the exact Core all the same, and [`core-over-time`](../checks/core-over-time/) recounts them.

## Inspecting the store

Open a copy, so that the archived bytes do not change:

```sh
cp store.sqlite /tmp/kafka-meaning-model.sqlite
sqlite3 -readonly /tmp/kafka-meaning-model.sqlite
```

Models are stored as changes on a base model, so reading a whole model is easiest through the tool: run the Meaning Model server with `LIFE_SIM_STATE_FILE` set to the absolute path of a copy. This is a server database, not a bundle for the model-import tool. The paper links a hosted rendering.

The original host configuration, launcher and raw session journals are not included, so this folder is an archive of the reading, not a self-contained reconstruction environment.
