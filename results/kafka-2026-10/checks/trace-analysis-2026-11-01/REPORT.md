# Third pass on the Meaning Model reading

1 November 2026. This only read what exists: the reading's 45 reflections placed in the story, and its recorded predictions and hypotheses. It redid nothing and did not touch the store. Eight Sonnet 5.5 calls at high effort, no tools, with no failures.

Files: `development/results`, `outcomes/results`, `build_third_pass.py`, `summarise_third_pass.py` (the count, following October's `dev_summary.py`, `per_pause.py` and `outcomes_summary.py`), `summary.json`, `summary-output.txt`.

## The table's seven rows

| Row | January | Understanding Graph | Meaning Model reading |
|---|---|---|---|
| Pauses revising an earlier view on new text | 8 of 28 | 20 of 57 | **18 of 41** |
| Expectations stated in reflections | 10 | 28 | **6** |
| … not borne out | 0 | 10 | **0** |
| Recorded expectations the story settles | 13 | 27 | **11** |
| … marked by the reading | 3 | 21 | **6** |
| Pauses reaching back at least 10% of the story | 10 of 28 | 26 of 57 | **19 of 41** |
| Pauses declining to infer beyond the text | 0 of 28 | 55 of 57 | **37 of 41** |

Other figures:
- 45 reflections analysed, none missing, 4,442 words.
- Revisions: 2 overturn, 20 qualify, 3 correct, 3 bookkeeping.
- Outcome reports in reflections: 12 (5 confirmed, 3 partly, 1 refuted, 3 still open), all rated right.
- 51 refusals. 59 references back, 54 doing work, 34 located in the story.
- Recorded notes: 58, of which 13 are real forward expectations. Of those, 8 borne out, 2 partly, 1 not borne out, 2 never settled.

## What it means

**This reading does well on revising, reaching back and declining to infer, but its expectations rarely fail.** That the story "sometimes proved wrong" a reading's expectations, "and said so", is true of the Understanding Graph reading (10 of 28). It is not shown for this one:

- None of the six expectations in its reflections fails, and at least three (reflections 2, 7, 29) offer alternatives, so they could hardly fail.
- The one refuted report (reflection 23) concerns what Gregor imagined, but reflection 22 itself raised "a possible lunge", so this refutation is fairer than a first reading suggested. It is still a report in the reflections, not one of the six expectations the table counts.
- The one record the checker calls not borne out is contested. `u33.forecast` gave the next dawn .55 alive without improvement and .25 dead. The book says he lived to see the light begin, then died. The reading scores this as the .55 under its own first-status terms (`u35.forecast-contract`), and warns that it is "a narrow boundary case" and no claim to have anticipated the ending (`u42.forecast-settlement-sensitivity`, reflection 39).
- The nearest thing to "said so" is `u03.adjudication`, which invalidates the strong version of `u02.prediction`.

**What the count misses.** This reading writes probabilities before the text and scores them after it. `u05`, `u15` (with a corrected calculation), `u20`, `u22` and `u35` score five such forecasts. `u22` settles one as a miss on its own strict terms, because the deadline could not be certified. That has no counterpart in the other readings, and the table does not show it.

## What was checked

Claude (Opus 5.5) made these checks.

- All 156 quotes of the reflections are exact, and all 27 `prompted_by` quotes are in the book (automatic check).
- I read all 12 outcome reports, all 6 expectations, all 11 settled records, the 5 overturns and corrections, and random samples of 6 of the 19 counted revisions and 5 of the 51 refusals (seed 20261101). These looked right, with two soft spots: reflection 26's "correct" concerns Gregor's belief more than the reader's, and "refusals" is a broad category that includes general restraint, as it did in October.
- The checker's "borne out" is generous for hedged expectations. Reflections 7, 29 and 30 count as borne out although little could have refuted them.
- My verification is not blind.
- I have since read the reading's seven `validates` and `invalidates` links: u03.adjudication→u02, u12.tested-care→u03, u15.reserve→u14, u22.wound-substance→u21, u27.christmas→u24.calendar-applied, u28.forecast-result→u25, u39.authority-result→u38. They look right within their stated scope. That read is mine and not blind, unlike the check on the Understanding Graph's 22, so the paper makes no claim about them.
