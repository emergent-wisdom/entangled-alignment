# Entangled Alignment: When Safety Is the Substrate

[![Paper](https://img.shields.io/badge/Paper-PDF-red)](paper/entangled-alignment.pdf)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.16440311.svg)](https://doi.org/10.5281/zenodo.16440311)
[![Code: MIT](https://img.shields.io/badge/Code-MIT-green)](LICENSE)
[![Content: CC BY 4.0](https://img.shields.io/badge/Content-CC%20BY%204.0-lightgrey)](LICENSE-CONTENT)

Companion repository for *Entangled Alignment: When Safety Is the Substrate*. The
paper proposes learning capability and care together throughout pretraining:
a continuing Reader's questions, judgments, and belief revisions become
training material alongside the sources it reads. Reader augmentation,
persistent graph memory, and Reader-Core stability are separately testable
hypotheses.

The code here is a working research prototype of the Teacher-side annotation
pipeline: a multi-agent system that reads a source chronologically, builds a
shared Understanding Graph, synthesizes its findings, and renders them as
prose. The January runs used Gemini 3 Flash Preview. Two later Kafka readings,
in October and November 2026, used GPT-6.1 Sol, taking the roles in turn within
one conversation at a time, with an Understanding Graph or a Meaning Model as
their store. They demonstrate the construction workflow; no Student has yet been
trained.

## The later Kafka readings

Explore the two later readings of *The Metamorphosis* in your browser:

- **Understanding Graph (October 2026):** [interactive graph](https://emergentwisdom.org/entangled-alignment/?project=metamorphosis) · [reading records](results/kafka-2026-10/understanding-graph-reading/).
- **Meaning Model (November 2026):** [interactive model](https://emergentwisdom.org/meaning-model/metamorphosis-reading/) · [reading records](results/kafka-2026-10/meaning-model-reading/).

The [archive](results/kafka-2026-10/) includes their stores, Reader thoughts,
source edition, run settings, prompts and the checks
reported in the paper. Its README explains how to inspect the records and
which parts of the original execution environment are not included.

The January stores remain in `projects/`; they have not been replaced by the
later readings.

## Browse the included graphs

The two January graphs ship with the repo — no API key needed to explore them:

```bash
git clone --recursive https://github.com/emergent-wisdom/entangled-alignment
cd entangled-alignment
./setup.sh
./view.sh        # opens http://localhost:3000
```

Select a project in the sidebar:

- **metamorphosis** — Kafka's *The Metamorphosis* (346 active nodes)
- **llada** — the LLaDA paper on large language diffusion (285 active nodes)

Click any node to see its content, edges, and the passage that produced it. If the
graph stays blank on your first visit, reload the page. If port 3000 is taken,
`PORT=3001 ./view.sh`.

## Run your own

`setup.sh` creates a `.env` file from `.env.example`. Open it and add your Gemini API key:

```
# Get your API key from https://aistudio.google.com/apikey
GOOGLE_API_KEY=your-key-here
GEMINI_MODEL=your-model-id
```

The runner reads `.env` with `python-dotenv`, including quoted values and inline
comments. Variables supplied in the environment take precedence.

Then run the agents on any text:

```bash
./run.sh /path/to/reviewed-book.txt --project my-reading --fresh-reading
```

New graphs and traces are kept in ignored `.local-work/projects/` and
`.local-work/traces/` until reviewed for release. To watch a new reading:

```bash
PROJECT_DIR="$PWD/.local-work/projects" ./view.sh
```

Use `--resume` with the same source and project to continue after interruption.
The viewer uses the same `UG_CLI` override. The checkpoint records exact passage
offsets, node IDs, the randomly selected workers and completed phases.
Pending reflection on the final passage runs even when source progress is 100%.
The runner stops after three rounds without reading progress and reports API or
MCP failures instead of silently treating them as completion. Synthesis and
translation must pass persisted-output checks before their phase completes.

The active prompt treatment is
`restored-exploratory-teacher+wisdom-2026-10-06+demonstration-2026-10-09`. Each
round uses a fixed complete-paragraph boundary (target 2,000 UTF-16 characters by default),
fresh agents, and the shared graph. Supply `--chunk-plan plan.json` for a pinned
comparison excerpt, `--source-provenance provenance.json` for its edition record,
and `--worker-schedule schedule.json` to reuse saved random choices. Temperature
defaults to 1.0 and can be set explicitly. No claim is made that fresh history
removes a model's pretrained knowledge of a story.

Private run outputs include the composed prompts and tool schemas,
`run_manifest.json`, `run_events.jsonl`, `worker_schedule.json`, the checkpoint,
the chronological `reading.md` export, and a source/Core/reference audit.
Every invocation and resume is recorded; a changed source, model, prompt or
tool identity is refused on resume. Historical graphs and exports keep their
original treatment.

### A reading in one persistent conversation

The October Understanding Graph reading was not run by these fresh agents.
`chronological_metacognition/agent_driver.py` lets one outside agent take every
perspective in turn, in one conversation, and audits each turn afterwards. That
reading used these settings:

```bash
.venv/bin/python chronological_metacognition/agent_driver.py setup /path/to/workspace \
  --source results/kafka-2026-10/source/metamorphosis-johnston.txt --project my-reading \
  --ug-cli node_modules/understanding-graph/bin/cli.js \
  --reader-chosen --persistent-economy --several-nodes
```

Then open a Codex session in that workspace as a trusted project. It follows
`AGENTS.md`: `./reading next` prints each turn's task and `./reading done` reports
it. With these settings the driver writes that reading's published prompts byte
for byte, apart from the project name and source id. The reading itself ran on
the code prepared for release as Understanding Graph 0.2.0; version 0.2.1, pinned
here, differs from that in comments, test fixtures, and the wording of one tool
description and two diagnostic messages.

The November Meaning Model reading ran differently again: one agent modeled the
book with the Meaning Model's own tools and took the text through the reading
mode in [`reading-mode/`](reading-mode/), whose README says how to load it. Its
prompts and settings are in `results/kafka-2026-10/meaning-model-reading/`.

### What a run costs

Measured from the shipped traces:

|                | Metamorphosis | LLaDA  |
| -------------- | ------------- | ------ |
| LLM calls      | 162           | 120    |
| Input tokens   | ~1.5 M        | ~1.1 M |
| Graph tool calls | 1,997       | 1,339  |
| Active time    | ~7 h          | ~5 h   |
| Wall clock     | 47 h          | 24 h   |

Active time is the time recorded inside the pipeline. The wall-clock figures are
much larger because each `swarm.jsonl` spans several resumed invocations rather
than one continuous session. The Metamorphosis trace records roughly 18 hours in
explicit `429 RESOURCE_EXHAUSTED` cooldowns; other gaps may include manual pauses,
which the released metadata cannot reconstruct precisely.

Both shipped readings completed. For Metamorphosis, the source record reaches
`position = total_length` (140,527 characters) with status `completed`, the final
run summary reports 100%, and the append-only trace reaches `Content 100%` and a
successful final translation. The 88% figure is only the latest Content marker
retained in the released database's graph tables. The complete chronological
Markdown export continues beyond that snapshot. Rate limits and manual restarts
may explain pauses between invocations, but 88% is not where the reading stopped.

## Prerequisites

- Python 3.10+
- Node.js 22+ (the graph store uses better-sqlite3 13)
- A [Gemini API key](https://aistudio.google.com/apikey) (only needed for running new texts)

## How it works

In the shipped runs, a Reader streamed the source chronologically, pausing at *Thought Moments* — emotional peaks, contradictions, conceptual shifts. The revised treatment fixes passage boundaries in advance and creates fresh agents for each phase, with the shared graph carrying understanding forward. Specialized Workers (Skeptic, Psychologist, Axiologist, Belief Tracker, Critic, Speculator, Connector and Curator) contribute typed nodes and edges. A Synthesizer draws their competing readings into a thought anchored to the Reader Core, and a Translator renders it as fluid prose. The shipped runs used eleven agents.

Everything is written to a shared knowledge graph via an MCP server (`understanding-graph`). The web frontend renders the graph as an interactive 3D visualization — nodes appear as the agents work, edges form between related concepts, and clusters emerge as themes develop.

## Relationship to understanding-graph

This repo uses [understanding-graph](https://github.com/emergent-wisdom/understanding-graph) as its MCP server — the shared memory that agents read from and write to. The two projects have diverged in how they teach agents to use the graph:

- **entangled-alignment** uses **prompt composition** — modular markdown files in `prompts/` that are assembled into system messages for Gemini swarm agents. This is the approach described in the paper and it works. The prompts ship with this repo and are self-contained.

- **understanding-graph** has moved to a **Claude Code skills** model — each skill is a standalone teaching unit that Claude Code loads natively. This is the newer approach for interactive use.

This repo carries its own copy of the prompts that the swarm agents depend on,
and pins the published dependency to `understanding-graph@0.2.1`. The reader
fails if the selected build is missing or has another version: `--ug-cli` or
`UG_CLI` selects another build, and `--require-tool-version` names the version
it must have. A selected checkout also needs the optional
`@huggingface/transformers` peer in its own dependency tree. The runner checks local 384-dimensional inference
before invoking a reading model and records the runtime and cached model hashes.
The reader uses
`TOOL_MODE=synthetic_reader`, which enables its reserved thinking creation and
translation tools. `setup.sh` installs the toolchain locally from
`package-lock.json`.

The shipped graphs (January 2026) predate that versioning scheme: at the time
`understanding-graph` was consumed as a git submodule and had no released
versions. The current toolchain is an update for new readings; it does not
reproduce the original runs byte for byte.

## Repository structure

```
├── setup.sh                      # One-time setup
├── run.sh                        # Run agents on any text file
├── view.sh                       # Launch the web viewer
├── .env.example                  # API key template
├── package.json                  # Pinned understanding-graph + embedding backend
├── package-lock.json             # Exact Node dependency tree (npm ci)
├── requirements.txt              # Pinned Python dependencies
├── paper/                        # The paper (LaTeX source, house style, PDF)
├── prompts/                      # Agent system prompts (from understanding-graph)
│   ├── core/                     # Philosophy, identity, five laws
│   ├── roles/                    # Agent identities (reader, skeptic, synthesizer...)
│   ├── modes/                    # Phase-specific behavior (reading, thinking)
│   ├── tools/                    # Graph tool usage guides
│   └── workflows/                # Orchestration patterns
├── chronological_metacognition/  # Agent code
│   ├── run_reader.py             # Main orchestrator (fresh agents, Gemini)
│   ├── agent_driver.py           # One outside agent taking every perspective
│   └── material/                 # Sample texts
├── reading-mode/                 # Meaning Model add-on that gives a book as it is read
├── orchestrator/                 # Agent coordination library (submodule)
├── projects/                     # Output graphs (one folder per run)
│   ├── metamorphosis/            # Kafka, January 2026 — included
│   └── llada/                    # LLaDA paper — included
└── results/
    └── kafka-2026-10/            # The later Kafka readings and their checks
```

## Citing

The DOI below identifies the November 2, 2026 published version.

```bibtex
@misc{westerberg2026entangled,
  title        = {Entangled Alignment: When Safety Is the Substrate},
  author       = {Westerberg, Henrik},
  year         = {2026},
  month        = nov,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.23887330},
  url          = {https://doi.org/10.5281/zenodo.23887330}
}
```

See [`CITATION.cff`](CITATION.cff) for the machine-readable version (GitHub
renders a "Cite this repository" button from it).

## License

Original software and operational prompts are licensed under the
[MIT License](LICENSE). Original paper, documentation, data, and research
artifacts are licensed under
[Creative Commons Attribution 4.0 International](LICENSE-CONTENT), only to the
extent that Henrik Westerberg holds the relevant rights.

The included source texts for *Metamorphosis* and *Large Language Diffusion
Models* are not covered by those licenses. See the exact path-level
[license map](LICENSES.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
