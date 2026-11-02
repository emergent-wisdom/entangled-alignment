# Checks of the later Kafka readings

These are the recorded evaluations cited in the paper's account of the two later
readings. They compare one January reading, the October Understanding Graph
reading and the November Meaning Model reading, not controlled replications of
one method. The source editions, reading models, tools and prompts differ. Each
report states its limits and its verification method.

## Contents

- `faithfulness-check/`: 85 blinded reflections (28 January, 57 Understanding
  Graph), the source horizon and current passage for each, the evaluator prompt,
  every result, the unblinding map, and verification judgments.
- `meaning-model-check/`: the same check on the Meaning Model reading's 45
  reflections, with the same prompt, and a read-ahead check of all 8,228 of its
  model changes in 159 record packets. It holds the packets, every result, the
  record prompt and a report with its verification.
- `core-check/`: 130 reflections (28 January, 57 Understanding Graph, 45 Meaning
  Model) with the Core recital removed, the blind ratings, their map to the
  readings, and verification notes.
- `core-over-time/`: the Core recital and Core reasoning in reading order, for
  all three readings, recomputed from the stores and the recorded ratings.
- `trace-analysis-2026-10-28/`: extracted scientific records for January and the
  Understanding Graph reading, development and expectation-outcome packets and
  results, their summaries, and the 20 planted error packets/results used to
  check evaluator recall and test–retest stability.
- `trace-analysis-2026-11-01/`: the same development and expectation-outcome
  pass on the Meaning Model reading, with its summary and report.
- `baseline/january-baseline.json`: the January source boundaries and pause
  mapping used by these scripts. Its input paths are relative to this file.

The blind evaluator was Claude Sonnet 5.5 at high reasoning effort, without
built-in tools or MCP servers. The qualitative verification notes identify
Claude Opus 5.5 as their reader. They describe an additional model
verification pass, not evidence of an independent human review. Some Core-rating
checks used only the first 650–700 characters, as their verification file
states. The Meaning Model reading's verification was not blind: the same session
had already read the whole reading, as its reports state. The results and
caveats are preserved.

## Verify or recompute without model calls

The per-packet scientific inputs and results are preserved. `MANIFEST.json`
records each published file's SHA-256. This archive contains no raw CLI journals,
account configuration or authentication data.

Use a separate private working copy if you regenerate anything: some analysis
scripts write their derived JSON files beside themselves. From the `checks/`
folder in that copy, these commands use only recorded results:

```sh
python3 faithfulness-check/aggregate.py
python3 core-over-time/core_over_time.py
python3 trace-analysis-2026-10-28/care.py
python3 trace-analysis-2026-10-28/dev_summary.py
python3 trace-analysis-2026-10-28/outcomes_summary.py
python3 trace-analysis-2026-10-28/pauses.py
python3 trace-analysis-2026-10-28/per_pause.py
python3 trace-analysis-2026-10-28/recall_score.py
python3 trace-analysis-2026-11-01/care_by_pause.py
python3 trace-analysis-2026-11-01/summarise_third_pass.py ../meaning-model-reading/store.sqlite
```

`trace-analysis-2026-10-28/per_pause.py` applies only to a `traces.json` holding
several reflections at a pause. `traces.json` holds January and the Understanding
Graph reading, which write one each, so it reports that and stops. The Meaning
Model reading's figures by pause come from `trace-analysis-2026-11-01/`.

The scripts that use a story read the exact Johnston source at
`../source/metamorphosis-johnston.txt`, the October Understanding Graph at
`../understanding-graph-reading/store.db`, the Meaning Model reading at
`../meaning-model-reading/store.sqlite`, and the January store at
`../../../projects/metamorphosis/store.db`. They open databases read-only.

`trace-analysis-2026-10-28/extract.py` rebuilds `traces.json` from those stores.

To rebuild packets, do so in a working copy with its corresponding old packets
and index removed. The source-faithfulness and Core builders assign new random
blind IDs; content should be compared using their mappings, not by assuming the
new IDs match. `build_recall.py` also assigns new blind IDs. Existing published
IDs and their result associations must be kept together. The Meaning Model
reading's builders keep their IDs and take the store and the record of its reads:

```sh
python3 meaning-model-check/build.py ../meaning-model-reading/store.sqlite ../meaning-model-reading/reads.json
python3 trace-analysis-2026-11-01/build_third_pass.py ../meaning-model-reading/store.sqlite
```

## Optional new model evaluations

The portable copies of `run_checks.py` and `run.py` use the Claude CLI. Set
`CLAUDE_CLI` to the executable you intend to use, or put `claude` on `PATH`.
They require an explicit `--execute` flag. These commands can incur charges and
are not part of the offline verification above. Their original model and effort
settings remain visible in the scripts and recorded results. Model availability
and future outputs may differ; new evaluations cannot be expected to reproduce
these judgments exactly.

Run new evaluations only in a private working copy. Existing result files are
kept, so remove only that copy's results if you intend to obtain fresh ones. For
example, from its `core-check/` directory:

```sh
python3 run.py --execute --only C-007785 --workers 1
```

For the planted-error check, its prompt is the source-faithfulness prompt:

```sh
python3 trace-analysis-2026-10-28/run.py recall --execute \
  --prompt faithfulness-check/PROMPT.md --key misreadings --workers 1
```

## Portability

Analysis scripts use repository-relative inputs. Optional evaluator runners use a caller-selected Claude
CLI, require `--execute`, and stop on any nonzero exit. The reports still name the
models that produced judgments and retain the experimental limitations.

The archive contains the final recorded judgments and the inputs needed to
inspect them. Reflections, evaluation packets, results and verification judgments
are as recorded. The recorded results are evidence about these particular readings;
they do not establish training effectiveness or a causal benefit of the Core.
