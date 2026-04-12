# Entangled Alignment: Cultivating Character in Pretraining

[![Paper](https://img.shields.io/badge/Paper-PDF-red)](paper/entangled-alignment.pdf)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19462868.svg)](https://doi.org/10.5281/zenodo.19462868)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A multi-agent system that reads a book chronologically and builds a knowledge graph of its concepts, relationships, and emergent themes — using Gemini-powered agents coordinated through an MCP (Model Context Protocol) server.

## Browse the included graphs

Two completed runs ship with the repo — no API key needed to explore them:

```bash
git clone --recursive https://github.com/emergent-wisdom/entangled-alignment
cd entangled-alignment
./setup.sh
./view.sh        # opens http://localhost:3000
```

Select a project in the sidebar:

- **metamorphosis** — Kafka's *The Metamorphosis* (350 nodes)
- **llada** — the LLaDA paper on large language diffusion (290 nodes)

Click any node to see its content, edges, and the passage that produced it.

## Run your own

`setup.sh` creates a `.env` file from `.env.example`. Open it and add your Gemini API key:

```
GOOGLE_API_KEY=your-key-here   # ← replace with your key from https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-3-flash-preview
```

Then run the agents on any text:

```bash
# Run on the bundled Twenty Thousand Leagues
./run.sh chronological_metacognition/material/pg164.txt --project verne

# Or on any text file
./run.sh /path/to/book.txt --project my-reading
```

Open `./view.sh` in a second terminal while the agents run — nodes and edges appear in the 3D graph in real time as each passage is processed.

## Prerequisites

- Python 3.10+
- Node.js 18+
- A [Gemini API key](https://aistudio.google.com/apikey) (only needed for running new texts)

## How it works

Three agents read a text sequentially, each processing the same passage with a different lens:

1. **Concept Extractor** — identifies key concepts and definitions
2. **Relationship Mapper** — finds connections between concepts
3. **Theme Synthesizer** — detects emergent themes and meta-patterns

Their outputs are written to a shared knowledge graph via an MCP server (`understanding-graph`). The web frontend renders the graph as an interactive 3D visualization — nodes appear as the agents work, edges form between related concepts, and clusters emerge as themes develop.

## Relationship to understanding-graph

This repo uses [understanding-graph](https://github.com/emergent-wisdom/understanding-graph) as its MCP server — the shared memory that agents read from and write to. The two projects have diverged in how they teach agents to use the graph:

- **entangled-alignment** uses **prompt composition** — modular markdown files in `prompts/` that are assembled into system messages for Gemini swarm agents. This is the approach described in the paper and it works. The prompts ship with this repo and are self-contained.

- **understanding-graph** has moved to a **Claude Code skills** model — each skill is a standalone teaching unit that Claude Code loads natively. This is the newer approach for interactive use.

The two systems are not interchangeable. This repo is pinned to `understanding-graph@0.1.15` (the version used for the paper results) and carries its own copy of the prompts that the swarm agents depend on.

## Repository structure

```
├── setup.sh                      # One-time setup
├── run.sh                        # Run agents on any text file
├── view.sh                       # Launch the web viewer
├── .env.example                  # API key template
├── prompts/                      # Agent system prompts (from understanding-graph)
│   ├── core/                     # Philosophy, identity, five laws
│   ├── roles/                    # Agent identities (reader, skeptic, synthesizer...)
│   ├── modes/                    # Phase-specific behavior (reading, thinking)
│   ├── tools/                    # Graph tool usage guides
│   └── workflows/                # Orchestration patterns
├── chronological_metacognition/  # Agent code
│   ├── run_reader.py             # Main orchestrator
│   └── material/                 # Sample texts
├── orchestrator/                 # Agent coordination library (submodule)
└── projects/                     # Output graphs (one folder per run)
    ├── metamorphosis/            # Kafka — included
    └── llada/                    # LLaDA paper — included
```

## Citing

```bibtex
@misc{westerberg2026entangled,
  title        = {Entangled Alignment: When Safety Is the Substrate},
  author       = {Westerberg, Henrik},
  year         = {2026},
  month        = apr,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.19462868},
  url          = {https://doi.org/10.5281/zenodo.19462868}
}
```

See [`CITATION.cff`](CITATION.cff) for the machine-readable version (GitHub
renders a "Cite this repository" button from it).

## License

MIT
