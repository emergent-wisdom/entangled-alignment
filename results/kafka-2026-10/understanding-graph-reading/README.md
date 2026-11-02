# Understanding Graph reading

One persistent Codex conversation using GPT-6.1 Sol at high reasoning effort read the Johnston text in 57 Reader-chosen pauses. The conversation took 697 requests and 169.4M input tokens, 99.4% of them cached, and was compacted once. The two Workers at each pause were selected with seed 20261009. `run-settings.json` preserves the worker schedule, scientific prompts, tool version identifiers and fingerprints. The runtime was the build prepared for Understanding Graph 0.2.0; its package versions retain the earlier development labels recorded by the run.

`store.db` is the exact final pinned SQLite store. It includes all stored tables, node and edge revisions, commits and tool-call records; no data was removed from it. `reading.md` is the original chronological prose export. `reflections.md` separately presents every raw Synthesizer thought and its prose rendering, in source order.

The store can be inspected read-only with SQLite. To avoid changing the archived bytes, open a copy when using an application that writes to the database. Its project metadata is in `project-meta.json`. The paper links a hosted rendering.

The prompts are the original bytes. The run-settings record removes host-specific paths, the operator's name and unrelated working-tree status. Runtime hashes remain unchanged; normalized metadata has a separate published checksum in `../ARTIFACT-MANIFEST.json`. The original host configuration and launcher are not included, so this folder is an archive of the reading, not a self-contained reconstruction environment.
