# Source-faithfulness check: January's reading against the several-nodes reading

Report and verification by Claude (Opus 5.5), 26 October 2026. A blind Claude Sonnet 5.5 pass compared each reflection with the passages available when it was written.

## Result

The several-nodes reading is far more faithful to the text than January's.

| | January (Gemini 3 Flash, Wyllie translation) | Several nodes (Sol high, Johnston translation) |
|---|---:|---:|
| Thoughts checked | 28 | 57 |
| Factual statements about the text the checker examined | 494 | 839 |
| Statements per 1,000 words of reflection | 52 | 85 |
| Misreadings the checker reported | 86 | 12 |
| Reported findings verified by me | 50: all 38 high and medium, and a random 12 of the 48 low | all 12 |
| **Confirmed misreadings** | **29** (2 high, 20 medium, 7 low) and an estimated 21 more among the 36 unverified low findings | **7** (0 high, 2 medium, 5 low) |
| **Thoughts with at least one confirmed misreading** | **20 of 28** | **6 of 57** |
| **Claims taken from text the reader had not read yet** | **10, in 6 thoughts** | **0** |
| Confirmed misreadings per 100 statements | at least 5.9, about 10 with the estimate | 0.8 |

The several-nodes reflections make more factual statements per word, and still misread about one tenth as often.

## January's misreadings (confirmed examples)

- **Thought 2 (high):** "The silence of his family is even more chilling". In the passage read, his mother, father and sister all knock and call to him.
- **Thought 2:** the family has "stopped seeing him as a person who *could* be ill". His sister asks "Aren't you well? Do you need anything?"
- **Thought 7:** "coffee pouring over her". The coffee pours onto the carpet.
- **Thought 8:** he wakes to "total stillness". Footsteps and a closing door wake him.
- **Thought 9:** his room is "a cell locked from the outside". The doors stand unlocked.
- **Thought 13:** his work was an "unnecessary sacrifice" for "a surplus they already possessed". Part of the surplus was his own saved earnings, and the old savings were too small to live on.
- **Thought 14:** the ceiling-hanging is "the first time" Gregor enjoys his existence. He already felt "alright with his body" and ate "his eyes watering with pleasure".
- **Thought 16:** the women "cart away the writing desk". They only threaten to.
- **Thought 19:** "a tender memory of a cashier". The tender memory is the chambermaid.
- **Thought 23:** "the family celebrates their 'exorcism'". There is only Grete's "At last!", while the parents sit silent or asleep.
- **Thought 24 (high):** "As his shell is shoved across the floor, Grete's exclamation of 'At last!' rings out". She says it the night before, when locking him in; the cleaner shoves him the next morning.
- **Thought 26:** the cleaner was "the only one who didn't look away from the corpse". Grete "had not taken her eyes from the corpse".

## January's claims ahead of the text

These statements are true of the book, but they come from text the reader had not yet read. That breaks the fresh-reading discipline; they are not misreadings of the story.

- **Thought 9:** Gregor's "relief" under the couch. The passage read stops mid-word at "he was no longer able to li"; the next sentence says he "felt immediately at ease".
- **Thought 11:** the family's "financial talk". The finances are explained pages later.
- **Thought 14:**
  - It quotes Gregor realising that "the lack of all direct human communication" has begun to "confuse his mind". Those are the book's words, from the next pause.
  - It has the mother clinging to the furniture as a "Human Map". Her speech against moving the furniture also comes in the next pause.
- **Thought 17:**
  - The mother "begs for the life" of Gregor. That is the next sentence after the passage read.
  - The father "wears his uniform even to sleep", which comes in Part III.
- **Thought 8:** "five years of dependence". That is first stated in a later passage.
- **Thought 24:** the family's new vitality, which comes after the passage read.

## The several-nodes run's confirmed misreadings (all of them)

- **Thought 5 (low):** "the lofty boss cannot hear". The text says he "has trouble hearing".
- **Thought 5 (low):** "his fantasy of knocking the boss off the desk". The text has the boss falling off it in shock.
- **Thought 6 (medium):** "He remembers an alarm … but cannot explain sleeping through it". He infers that it must have rung, and explains that he slept "all the more deeply".
- **Thought 14 (low):** "Gregor says the confident arrangements make him feel good". The text narrates the feeling; he says nothing.
- **Thought 18 (low):** "the father will not make room for turning". The father lets him turn and even guides him with the cane.
- **Thought 22 (low):** "hearing every sigh". The text has him listening "now and then".
- **Thought 42 (medium):** "The room that was almost emptied". Only the chest of drawers was carried out.

Three more findings are partly right (thoughts 15, 30 and 50). Two were rejected:
- **Thought 29's** reading of Grete's motive is supported by "For surely no one except Grete would ever trust themselves to enter".
- **Thought 32:** Gregor did plead to spare his parents, telling the manager "Make it easy on my parents!".

## Method

- **Packets.** Each of the 85 thoughts got one packet with four parts:
  - the text the reader had read when writing it: January's input from its graph's source table, and the Johnston edition for the new run;
  - the passage read just before it;
  - the raw thought and its translation, with the shared Core removed.

  The packets carry random IDs in shuffled order, so the checker was not told which reading a thought came from. The translation does give it away. Files: `build_packets.py`, `packets/`, `mapping.json`.
- **Checker.** Sonnet 5.5 at high effort, one call per packet. It had no tools and no MCP servers, and worked from an empty directory with the packet on stdin. Its instructions are in `PROMPT.md` and the runner is `run_checks.py`. All 85 calls succeeded; the checker reported $9.33 of usage.
- **Verification.** I read each verified finding against the source text, and in places against the text just past the pause. Verdicts are in `verification.json`; `findings.md` lists every reported finding, unblinded and marked. The verdicts:
  - **confirmed**;
  - **duplicate**: the same claim in both versions;
  - **ahead**: true later in the book, unread at the time;
  - **partly**;
  - **rejected**.

## Limits

- **Different translations** (Wyllie and Johnston) and **different models** (Gemini 3 Flash and Sol at high effort). This compares the two readings as made, not the method alone.
- **Thought length.** January's thoughts are about twice as long (about 335 words after the Core, against 171). The comparison per statement checked allows for this.
- **36 of January's low findings are unverified.** In the sample of 12: 7 confirmed, 3 partly right, 2 ahead of the text. The estimate above uses that rate.
- **One checker model.** A second checker would show how stable the findings are.
