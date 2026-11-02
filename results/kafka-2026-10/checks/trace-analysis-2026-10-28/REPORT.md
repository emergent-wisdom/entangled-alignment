# How the January and October Kafka readings develop: revision, expectation, memory and care (28 October 2026)

This is the second analysis of two readings of *The Metamorphosis*: January, and the Understanding Graph several-nodes reading of October. The first analysis checked accuracy, read-ahead and Core reasoning (`../faithfulness-check`, `../core-check`). This one asks what the paper's H1 and H2 rest on: does the reader form expectations, meet new evidence and revise; does it carry the earlier story into its reading of the present; whom does its care reach; and can the accuracy checker be trusted?

All blind passes used Claude Sonnet 5.5 at high effort, with no tools, through `run.py`. Every number below is from a single run of each reading and is descriptive. Source verification checks are in `VERIFICATION.md`.

## What each reading was told to do

Read every count below against the prompts.
- **The Understanding Graph reading:** its Synthesizer prompt (`../../understanding-graph-reading/prompts/perspectives/synthesizer.md`) contains these rules:
  - "You MUST look BACKWARD";
  - name earlier nodes explicitly in the text;
  - "make PREDICTIONS";
  - "RESOLVED PREDICTIONS ARE GOLD".

  Counts of citation, prediction and resolution therefore partly measure how well the reading followed its instructions.
- **Marking limits is prompted too.** Its shared instructions (`../../understanding-graph-reading/prompts/AGENTS.md`) hold "THE STANCE OF UNCERTAINTY" ("Hold conflicting ideas", "Embrace the 'Maybe'") and "The Constraint of Humility" ("You do not possess a Crystal Ball"); they tell the reader to "Separate what they say and do from your interpretation of their motives" and to "Make guesses that could be WRONG". The Synthesizer is told "Never state what WILL happen". The April bundle of January's lineage (`b762d4f`, `prompts/modes/fresh_reading.md`, `prompts/core/emergent_wisdom.md`) has the same passages. So January's zero is a failure to follow instructions it very probably had, and the Understanding Graph reading's high counts are compliance as much as character.
- **January:** its own prompt text is not in its trace. The prompts bundled in April from the same lineage (`b762d4f`) carry the same rules.
- **No baseline:** there is no context-only reading. Nothing here tests H2's causal claim.

## Units

The readings differ in length:
- **Pauses:** January's median passage is 3.3% of the story, and the Understanding Graph's 1.6%.
- **Reflections:** without the Core, January's reflections total 9,943 words, and the Understanding Graph's 9,951.

So distances are in fractions of the story, never in pauses. Counts are given with their denominators, or per 1,000 words. Both readings wrote one reflection per pause.

## 1. Expectations and how they were settled

### In the records

`build_outcomes.py` and `outcomes/` hold this check. Every record each reading marked as a prediction or hypothesis was judged blind against the whole story: is it a real expectation, what settles it, and where. `outcomes_summary.py` compares each verdict with the reading's own `validates`, `invalidates` and `contradicts` links.

| | January | Understanding Graph |
|---|---|---|
| Prediction or hypothesis records | 20 | 41 |
| Real expectations about later text | 13 | 29 |
| Borne out / partly / not / never settled | 8 / 4 / 1 / 0 | 13 / 6 / 8 / 2 |
| Settled by the story | 13 | 27 |
| … that the reading itself marked | 3 (one rests on read-ahead) | 21 |
| … that the reading named or linked again later | 6 | 26 |
| Median distance to the settling passage | 6.3% of the story | 3.3% |
| Settled 10% or more of the story later | 5 | 5 |

I read all 26 resolution links by hand (`resolution-links.txt`).
- **Understanding Graph:** its 22 links are all correct against the story.
- **January:** 2 of its 4 are genuine.
  - One is two Workers disagreeing within the same pause.
  - One "prediction" names the lodgers' exit and their threat of a lawsuit at 74% of the story. In the Wyllie text January read, the lodgers do not arrive until 76%. That is read-ahead in a Worker node; the accuracy check covered only the reflections.
- **Disagreement with the book:** one, in the Understanding Graph reading, and it is a matter of scope. The reader refuted "even a retreat will be absorbed" for the immediate turn, while the checker judged it borne out by the locking of the door.

### In the reflections

`build_development.py`, `development/` and `dev_summary.py` hold this pass. Each reading's reflections were placed in the story where they were written, followed by the unread rest, ten reflections analysed per call.

| | January | Understanding Graph |
|---|---|---|
| Expectations stated (in how many reflections) | 10 (9) | 28 (19) |
| … not borne out | 0 | 10 |
| Outcomes of earlier expectations reported | 4 | 23 |
| … reporting the reader wrong or partly wrong | 0 | 14 |
| … whose report the checker found right | 2 (2 unclear) | 23 |
| Per 1,000 words: expectations | 1.0 | 2.8 |

**The finding.**
- **January:** its reflections' expectations never fail, and they only ever report confirmations. Several are framings rather than testable guesses, such as "he has actually opened a gate to his own erasure", which the checker generously counted as borne out. One foresees the death: "their patience is a countdown to his own disappearance", at 68%.
- **The Understanding Graph reading:** it guesses and is wrong about a third of the time, and says so later.

Every model involved probably knows this story. So a correct expectation is weak evidence of discovery, and a failed one, stated and later corrected, is the behaviour H1 needs.

### Gregor's death

No reflection or record of the Understanding Graph reading predicted it. The nearest is a record written just before the death (91%). It feared that the locked room "will hide a need that cannot wait", which the reading later marked as borne out.

## 2. Revision

### In the reflections (development pass)

| | January | Understanding Graph |
|---|---|---|
| Interpretive revisions: overturn / qualify / correct | 1 / 11 / 0 | 5 / 21 / 0 |
| … prompted by newly read text | 9 | 25 |
| Reflections revising an earlier reflection's view on new text | 8 | 20 |
| Bookkeeping changes (dates, labels, statuses) | 0 | 0 |
| Per 1,000 words: interpretive revisions | 1.2 | 2.6 |

Both readings revise, and almost always by qualifying a view rather than giving it up. January's sampled revisions are real, but several reframe one metaphor as another ("Rigor Mortis of Authority" becoming "a preparation for a new kind of servitude").

### In the records

- **Understanding Graph:** no supersessions; 9 `invalidates` and 13 `validates` links, all on predictions.
- **January:** 2 supersessions. Of its 10 `contradicts` links, 4 are within the same pause and 2 point at nodes missing from the snapshot.

## 3. Reaching back: long-range memory

### In the text of the reflections

The development pass lists every reference back, with a phrase from the earlier moment. It also judges whether each reference changes how the present passage is read ("works") or only recalls the earlier moment ("cites").

| | January | Understanding Graph |
|---|---|---|
| References back (doing interpretive work) | 70 (46) | 92 (87) |
| Located 10% or more of the story back | 17 | 39 |
| Reflections using a moment 10% or more back that does work | 10 of 28 | 26 of 57 |

### By identifier

This is the mechanical count in `extract.py`. A reflection names, or links to, a record from at least 10% of the story earlier:
- January: 8 of 28;
- Understanding Graph: 1 of 57.

The graph records themselves reach that far back in 22 of 28 pauses (January) and 39 of 57 (Understanding Graph). So the Understanding Graph reading's graph holds the long-range links, but its reflections cite only the current pause's nodes and carry the past in words.

## 4. Declining to infer beyond the text

The development pass lists every explicit refusal to infer, predict or assume what the text has not given:
- January: none, in 28 reflections;
- Understanding Graph: 93, in 55 of 57 reflections (9.3 per 1,000 words).

**Example.** "I can see fear without making it the only thing in them" (Understanding Graph).

This marking of limits sits alongside the expectations above. It does not replace them: the Understanding Graph reflections state more expectations per word than January's.

## 5. Care for each person

`care.py` aggregates the `people` field of the blind Core-reasoning pass (`../core-check`). That field lists the people in the passage each reflection extends care or understanding to, and those it treats only as an obstacle, a symbol or a function. Names are normalised (sister/Grete, Mr Samsa/father, charwoman/cleaner, and so on).

| | January | Understanding Graph |
|---|---|---|
| Reflections treating someone present only as a function | 26 of 28 | 13 of 57 |
| Gregor: care / function | 21 / 7 | 57 / 0 |
| Grete | 6 / 14 | 33 / 0 |
| Mother | 4 / 17 | 27 / 4 |
| Father | 1 / 19 | 21 / 5 |
| Lodgers | 0 / 3 | 1 / 5 |
| Cleaning woman | 0 / 5 | 3 / 1 |
| Manager | 0 / 6 | 5 / 3 |

**What the lapses are,** read by hand for Grete and the father:
- **January reduces.** 12 of its 14 Grete entries cast her as a symbol, such as "a cruel logician who 'performed a surgical strike'", "The New Matriarch of Logistics" or "a technician managing a biological hazard".
- **The Understanding Graph's lapses** fall on people at the edge of a scene, above all the lodgers. They are treated "as inspectors and an echo of the boss's authority, not as individuals", in 5 of 6 ratings.

## 6. Does the checker catch what it should?

`build_recall.py` and `recall/` hold this test. I planted one error, written against the packet's own text, in copies of 20 reflections that had already been checked (seed 1028): ten per reading. Of these, 10 were claims taken from text not yet read, and 10 were misreadings of text already read. The same checker, with the same prompt and settings, was rerun on the copies.

- **Caught:** 20 of 20. All 10 read-ahead claims were reported as "invented" (3 high and 7 medium severity), and all 10 misreadings as high severity.
- **Limit:** planted errors are blunter than real ones, so this is an upper bound on recall for subtle errors.
- **Test–retest:**
  - January: on the same ten packets, the rerun found 19 of the 29 misreadings the first run had reported.
  - Understanding Graph: the ten packets had no findings in either run.

So the counts in the paper are approximate per run, but the gap between the readings is far larger than the run-to-run variation.

## 7. Where the readings paused (descriptive)

`pauses.py` locates 14 turning points in each translation, among them:
- the manager's arrival;
- the father driving Gregor back;
- the apple;
- the violin;
- "we must try to get rid of it";
- the death;
- the tram.

The median distance from a turning point to the next pause is 1.2% of the story (January) and 0.8% (Understanding Graph). That is about half the median passage in each reading, which is what pausing without regard to the turning points would also give. The readers pause at local shifts throughout. They do not single out the major turns.

## What was not measured

- **Depth or literary quality.** A model judge would repeat Test 1 with weak blinding, so it was not attempted.
- **The fidelity of the prose translation to the raw thought.**

## Files

- `traces.json` (`extract.py`): the two readings in one shape.
- `development/`: PROMPT, packets, results, `summary.json`.
- `outcomes/`: PROMPT, packets, results, `summary.json`.
- `recall/`:
  - `selection.json` and `plants.json`;
  - packets and results;
  - `score.json`.
- `care.json`, `pauses.json` and `resolution-links.txt`.
- `run.py`: the runner. It makes one call per packet, with no tools and an empty working directory, and stops on a nonzero CLI exit. It requires `--execute`; see the checks README before running new evaluations.
