"""Where each reading paused: passage lengths and the distance from turning points to the next pause.

    python3 pauses.py

Turning points are located in each translation by a short phrase, searched with whitespace collapsed (Johnston for the later readings, Wyllie
for January); distance is measured from the end of that phrase to the next pause, as a fraction of the story.
Writes pauses.json.
"""
import json
import re
import statistics
from pathlib import Path

from build_development import stories, utf16

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
# (label, Johnston phrase, Wyllie phrase)
TURNS = [
    ("the manager arrives", r"the manager himself", r"the chief clerk himself"),
    ("the lock opens", r"lock as it finally snapped open", r"lock as it snapped back"),
    ("the father drives him back", r"slammed shut with the cane", r"slammed shut with the stick"),
    ("the milk", r"filled with sweetened milk", r"filled with sweetened milk"),
    ("the savings", r"grown into a small capital", r"some interest had accumulated"),
    ("the picture", r"picture of the woman dressed in nothing but fur", r"lady dressed in copious fur"),
    ("the mother faints", r"Mother fainted, but", r"Mother.s fainted, but"),
    ("the apple lodges", r"drove into his back really hard", r"hit squarely and lodged in his back"),
    ("the lodgers arrive", r"to three lodgers", r"rented out to three gentlemen"),
    ("the violin", r"His sister began to play", r"His sister began to play"),
    ("\"we must try to get rid of it\"", r"we must try to get rid of it", r"we have to try and get rid of it"),
    ("the death", r"tower clock struck three", r"his last breath flowed weakly"),
    ("the lodgers are dismissed", r"Get out of my apartment immediately", r"Leave my home"),
    ("the tram", r"took the electric tram", r"took the tram out"),
]

def main():
    traces = json.loads((HERE / "traces.json").read_text())
    wyllie, johnston = stories()
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())["source_boundaries_utf16"]
    first, last = base["story_first_sentence"], base["gutenberg_end_marker"]
    texts = {"january": utf16(wyllie, first, last), "understanding-graph": johnston, "meaning-model": johnston}
    out = {}
    for name, reading in traces.items():
        text = re.sub(r"\s+", " ", texts[name])
        ends = sorted(p["end"] for p in reading["pauses"])
        lengths = [p["end"] - p["start"] for p in reading["pauses"]]
        rows = []
        for label, j, w in TURNS:
            phrase = w if name == "january" else j
            found = re.search(phrase, text)
            at = found.start() if found else -1
            if at < 0:
                rows.append({"turn": label, "found": False})
                continue
            pos = found.end() / len(text)
            after = [e for e in ends if e >= pos - 1e-9]
            rows.append({"turn": label, "found": True, "at": pos, "next_pause_after": (after[0] - pos) if after else None})
        located = [r["next_pause_after"] for r in rows if r.get("found") and r["next_pause_after"] is not None]
        out[name] = {"pauses": len(ends), "median_passage": statistics.median(lengths), "max_passage": max(lengths),
                     "turns_located": len(located), "median_turn_to_pause": statistics.median(located) if located else None,
                     "turns_within_1pct": sum(x <= 0.01 for x in located), "rows": rows}
        o = out[name]
        print(f"{name}: {o['pauses']} pauses, median passage {o['median_passage']:.3f} of the story; turning points located "
              f"{o['turns_located']}/{len(TURNS)}; median distance to the next pause {o['median_turn_to_pause']:.4f}; within 1%: {o['turns_within_1pct']}")
        for r in rows:
            if not r.get("found"):
                print("   not found:", r["turn"])
    (HERE / "pauses.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
