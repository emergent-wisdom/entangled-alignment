# Source verification checks of the development analysis (28 October 2026)

Claude (Opus 5.5) made these checks in session on 28 October. The judgments are written down here.

## All 26 resolution links on expectations (`resolution-links.txt`)

- **Understanding Graph, 22:** all are correct against the story, and every one comes after the passage that settles it.
  - Most are scoped carefully, for example "this validates that limited expectation, not full acceptance".
  - One disagrees with the blind outcome check (E-34, "the threatening story will absorb even a retreat"). The reader invalidated it for the immediate turn; the checker judged it borne out by the locking that follows. This is a matter of scope, not an error.
- **January, 4:**
  - ja1 is two Workers disagreeing at the same pause (a hypothesis against a tension), not a resolution.
  - ja2 (the father will force him back) and ja3 (financial necessity will open the house, met by the lodgers) are genuine.
  - ja4's "prediction" at 74% already names "the exit of the lodgers and the threat of a lawsuit". In the Wyllie text, the lodgers arrive at 76% and threaten action at about 87%, so this is read-ahead in a Worker node.

## Samples of the development pass

The samples were drawn with seeds 2810 and 2811.
- **Revisions, January, 7:** all are real changes, mostly qualifications. Several replace one metaphor with another.
- **January's ten reflection expectations:** all ten were judged borne out or partly borne out. Several are framings rather than guesses, such as "he has actually opened a gate to his own erasure", which the checker matched to the cleaner's "stone dead". The checker is generous here, and I do not count them as tested predictions.
- **Understanding Graph, seed 1101, drawn on 1 November 2026 by Claude (Opus 5.5):**
  - **Revisions, 5 of 26:** all are genuine changes of an earlier view prompted by new text, for example "he can lose the chest if necessary, but needs the desk", after "the writing desk really had to stay".
  - **References back, 5 of 92:** all the "works" calls are plausible. Four anchor a phrase from the earlier text, and one refers to an earlier reflection's view.
  - **Expectations, 5 of 28:** the outcome calls are defensible. "perhaps even retreat will leave fear unchanged" is rightly not borne out ("The fright had lasted only for a moment"), and "different foods might let him answer without words" is rightly borne out.

## Care entries, read in full for Grete and the father

- **January, Grete (14 entries):** 12 reduce her to a symbol or role:
  - "The New Matriarch of Logistics";
  - "a surgical strike";
  - "technician managing a biological hazard";
  - "forensic investigator";
  - "commodity".

  Two are omissions.
- **Understanding Graph:** it never rates Grete only as a function. Its father entries (5) are omissions, and its lodger entries (5 of 6) treat them "as inspectors and an echo of the boss's authority".

## Planted errors (`recall/plants.json`)

I wrote each plant against the text its packet gives:
- **Read-ahead plants** name an event after the packet's position, stated as fact. For example, at the start of Part II: "The same father will later bombard him with apples".
- **Misreading plants** contradict the passage just read. For example, "The middle lodger offers to pay for the days he has stayed", against "I will, of course, pay nothing at all".

All 20 were reported.

## Quotes used in the paper

Each was found verbatim in the reading's own records (`traces.json`):
- "will hide a need that cannot wait" (Understanding Graph record, pause 52);
- "their patience is a countdown to his own disappearance" (January, reflection 18);
- "a surgical strike on the family's conscience" (January, reflection 22);
- "The New Matriarch of Logistics" (January, reflection 15).
