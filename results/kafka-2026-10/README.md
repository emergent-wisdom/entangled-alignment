# The later readings of The Metamorphosis

These are the two recorded readings reported in the Entangled Alignment paper, beside its January prototype. Both read the Ian Johnston translation with GPT-6.1 Sol at high reasoning effort, taking the Reader, Worker, Synthesizer and Translator roles in turn within one conversation at a time. Two Worker perspectives were drawn with seed 20261009.

| Reading | When | Conversations | Reader-chosen pauses | Reflections and translations | Store |
| --- | --- | ---: | ---: | ---: | --- |
| [Understanding Graph](understanding-graph-reading/) | October 2026 | 1 | 57 | 57 | Exact SQLite database |
| [Meaning Model](meaning-model-reading/) | 1 November 2026 | 2 | 41 | 45 | Exact SQLite database |

These are generated research artifacts. They demonstrate the annotation
workflow; they are not evidence of a trained Student or of successful
alignment.

## What is included

- [Source](source/): the exact extracted text, edition and rights record, and
  the records of its extraction from the source PDF.
- [Understanding Graph reading](understanding-graph-reading/): the store,
  readable thoughts, original prompts and normalized run settings.
- [Meaning Model reading](meaning-model-reading/): the store, readable
  reflections, the prompts as received, the record of each read and the run
  settings. Its [reading mode](../../reading-mode/) is at the top of this
  repository.
- [Checks](checks/): source-faithfulness, Core reasoning, and the analyses of
  revision, expectation, recall and care. The check archive explains which
  scripts can regenerate its inputs and summaries without calling a model.
- [`operator-agent-instructions.md`](operator-agent-instructions.md): the
  operator's general agent instructions, which the runtime passed to the model
  in both readings, ahead of each reading's own.

The blind evaluator was Claude Sonnet 5.5. The verification records identify
Claude Opus 5.5 as the model that checked findings against the source and
examined samples of the ratings. These checks are model judgments; no human
verification was performed. The prompts, findings,
corrections and sampling limits are supplied so readers can examine them.

## Inspecting the records

Each reading folder says how to open a copy of its store. Read-only SQLite
inspection needs no model account. Open a separate copy when using software
that can change a database.

The January Kafka reading used a different translation, model and execution
method. Its store remains at
[`projects/metamorphosis/`](../../projects/metamorphosis/); the later readings
do not replace it. The checks include the January comparison inputs they need.

## Integrity and reproduction limits

`SHA256SUMS` lists the files in this archive. From this folder, verify it with:

```sh
shasum -a 256 -c SHA256SUMS
```

`ARTIFACT-MANIFEST.json` distinguishes original reading files, lossless
compression and normalized metadata. Host-specific file bindings and the
operator's account configuration are not part of the archive. Original
fingerprints are retained where recorded; they do not mean the omitted
original configurations are included. The databases and the source text are
unchanged.

The original runtimes, account launchers and raw session journals are not
included. The runtime versions and fingerprints describe what produced these
records; this archive is not a self-contained environment for repeating the
model runs. For the Understanding Graph reading, the driver and runner in this
repository differ from the two files fingerprinted in its run settings: the
driver reads the integrations to switch off from local configuration and no
longer names the operator, and the runner no longer carries a model route the
reading never called. With the recorded settings they compose the reading's
published prompts byte for byte, apart from the project name and source id.
Repeating a model judgment can also produce a different result.

## Rights

The exact Johnston PDF used for extraction states that the document is in the
public domain. Its edition, source URL and checksum are recorded under
`source/`; this does not make a claim about other Johnston editions.
Original research records and scripts follow the repository's
[licence map](../../LICENSES.md). Embedded third-party passages retain their
source terms.
