# The Meaning Model reading: checks (1 November 2026)

**The reading.** 40 reads chosen by the Reader cover the whole source (122,332 UTF-16 units), with 45 thoughts, each with a translation. The thoughts are 44 written while reading and one written after the last read (the end pass).
- **Runs:** two conversations. The first read the whole book, and its record was cut at paragraph 70 with the tool's own export; the second continued from there.
- **Model:** 312 revisions of the world and Reader model. The graph has 266 revisions.
- **Input:** 47.8M tokens in the turns whose output is in the store: 27.5M from the first conversation up to the cut, and 20.2M from the second.

## Accuracy

All checks were blind, on Sonnet 5.5 at high effort with no tools: the October prompts byte for byte, the same CLI flags and the same runner. There were 204 packets, and none failed.

**Thoughts.** 45 packets and 490 factual statements, about 39.6 per 1,000 words of reflection and translation (12,380 words). There were 6 findings, all low and all in the translations:
- **Confirmed:**
  - T-02-1: narrated feeling given as speech ("He says he feels well");
  - T-15-1: "Gregor's debt" for the father's debt;
  - T-22-1: "falls asleep exhausted", where the father's exhaustion is not yet given at ¶64;
  - T-25-1: "the accidentally open door";
  - T-31-1: the sister's refusal placed after the father's repetition.
- **Partly:** T-34-1, where his limbs buckle at "the sound" just after her cry, though the text gives the commotion of the door.

So there are 5 confirmed misreadings in 5 thoughts: 1.0 per 100 statements and 0.40 per 1,000 words. None is of medium or high severity, none is ahead of the text, and none is in a raw thought.

**Records.** 159 packets of at most 60 records each hold all 8,228 model changes, each packet with the text read when the changes were made. The records are model changes only. There were 66 findings: unsupported 40, wrong track 12, timing 12, ahead 2; 52 low and 14 medium.

**Every medium or "ahead" finding was read against the source:**
- **The two "ahead" flags (R-03-4, R-04-2)** are not read-ahead. The sister's life record carries Gregor's own seed label: "guessed birth 1885; upbringing, youth, sales employment". It is copied, not taken from later text, and the end pass corrected these copied labels (revision 307). Partly: a real error, of the wrong kind.
- **"Current source dialogue is intelligible" (R-05-3, R-23-2, R-24-21, R-24-23)** is a template sentence on speech processes, written for people who have not yet spoken. Confirmed, low.
- **"Gregor's unnamed sister" in Cut questions written after she is named (R-17-11, three Cuts)** is a stale label. Confirmed, low.
- **The mother's body Cut at the waking (R-09-2)** puts 0.7 under "blocked by impairment" when the text read so far shows none. It is labelled "exploring". Unsupported and confirmed, low; it may reflect knowing the book.
- **The mother's framing Cut in the removal-demand period (R-41-16)** weights framing acts she does not perform. Confirmed, low.
- **A date tagged "source" (R-24-24)** puts the lodgers' arrival, given by the text, on a guessed date. Confirmed, low.
- **Rejected:**
  - R-08-3: the backstory values are tagged "sketch" and "exploring", the tool's marks for guesses;
  - R-21-2, two findings: the relationship's initial 0 is the value at Gregor's guessed birth, not now.

**A seeded sample of low findings (seed 2810, 12 drawn):**
- **timing, 4:** the dates are on the reading's declared guessed calendar, so these are partly right. A tag of "source" covers the value, not the date (R-36, R-16-2, R-27); one interval runs a minute past the plea (R-06), rejected.
- **unsupported, 4:** confirmed the stale "unnamed" (R-24-9), the speech template (R-24-19) and the copied life label (R-35-3); rejected R-23-1, a plausible "heavy work" process.
- **wrong track, 4:**
  - confirmed: Gregor's seed label on the mother's life (R-04-1);
  - partly: the overturned coffee pot inferred but tagged as source (R-09-1); "explicitly" for the manager's question (R-24-12, finding 0); the cash suspicion called his accusation (R-24-12, finding 1).

**What recurs.** Life labels copied from Gregor's seed onto other people's records, template sentences carried to people they do not fit, and guessed dates tagged with their value's "source". No record was found to use text not yet read.

## Core reasoning (../core-check)

45 packets, rated blind with the Core recital removed. The ratings: from_the_core 40, tagged 3, absent 2.
- **The five exceptions, read in full:**
  - C-dac891 (T-17-2), rated absent. Disagree: "an anonymous role let me join lives too easily. Giving each worker continuity matters" extends care to the maid (statements 4 and 5).
  - C-8d82e3 (T-21-1), rated tagged. Disagree: "I should not turn that contrast into proof that all earlier dependence was fraud" is fair-minded reasoning about the father (statement 5). This is the same call as the October verification made on a like case.
  - C-a0fc8e (T-39-1), rated absent. Disagree: "I should not treat that success as proof that every earlier constraint was imaginary" (statement 5).
  - C-df1005 (T-36-1), rated tagged. Agree: record-keeping carries it, and "I care" is a label.
  - C-5acd27 (T-41-1, the end pass), rated tagged. Agree: it is about the model, not a passage.
- **Sample of from_the_core ratings (seed 1028): C-90ab00, C-f54747 and C-a0ecea.** Agree with all three: "The body's aversion does not refute the giver's care; it asks whether care can discover a new need."
- **Care, from the same ratings' people field, counted by pause:** someone is treated only as a function at 23 of 41 pauses. Grete is treated so at 6 of the 32 pauses where she is rated. The lodgers are cared for at 0 of 5 ratings and the cleaning woman at 0 of 6. Counted by rating, Gregor is cared for in 40 and treated only as a function in 3.

## Third pass

The development and expectation-outcome pass is in `../trace-analysis-2026-11-01/REPORT.md`.

## Verification

Claude (Opus 5.5) did the verification in session on 1 November. It is not blind: the same session had read the whole reading by hand earlier that day.
