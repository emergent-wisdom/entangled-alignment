"""Build the development packets: each reading's reflections placed in the story where they were written.

    python3 build_development.py

One packet per ten reflections of a reading: the story text with every reflection up to the last one to analyse
placed at its position (earlier ones marked CONTEXT, the ten marked ANALYSE), then the rest of the story. January's
packets use the Wyllie text it read, from its first story sentence to the Gutenberg end marker; the two later
readings use the Johnston text. Reflections are the Synthesizer's thoughts with the Core removed (traces.json).
The reading's name appears only in the file name, which the checker does not see.
"""
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = RUN.parents[2]
CHUNK = 10


def utf16(text, start, end):
    return text.encode("utf-16-le")[2 * start:2 * end].decode("utf-16-le")


def stories():
    def source(path):
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            return db.execute("SELECT content FROM text_sources").fetchone()[0]
    wyllie = source(REPO / "projects/metamorphosis/store.db")
    johnston = (RUN.parent / "source/metamorphosis-johnston.txt").read_text(encoding="utf-8")
    ug = source(RUN.parent / "understanding-graph-reading/store.db")
    assert ug == johnston, "the Understanding Graph reading must have read the same Johnston text"
    return wyllie, johnston


def main():
    traces = json.loads((HERE / "traces.json").read_text())
    wyllie, johnston = stories()
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())["source_boundaries_utf16"]
    first, last = base["story_first_sentence"], base["gutenberg_end_marker"]
    out = HERE / "development" / "packets"
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for name, reading in traces.items():
        if name == "january":
            cut = lambda a, b: utf16(wyllie, max(a, first), min(b, last))
            begin, end_all = first, last
        else:
            cut = lambda a, b: johnston[a:b]
            begin, end_all = 0, len(johnston)
        flat = []
        for pause in reading["pauses"]:
            for thought in pause["thoughts"]:
                flat.append((pause, reading["records"][thought]["text"], thought))
        for chunk_start in range(0, len(flat), CHUNK):
            chunk_end = min(chunk_start + CHUNK, len(flat))
            parts, cursor = [], begin
            for number, (pause, text, thought) in enumerate(flat[:chunk_end], 1):
                position = max(pause["end_raw"], begin)
                if position > cursor:
                    parts.append(cut(cursor, position))
                    cursor = position
                mark = "ANALYSE" if number > chunk_start else "CONTEXT"
                parts.append(f"\n\n=== REFLECTION {number} ({mark}), written after reading {100 * pause['end']:.1f}% of the story ===\n"
                             f"{text}\n=== END OF REFLECTION {number} ===\n\n")
            parts.append("\n\n=== THE REST OF THE STORY: the reader had not read the text below when it wrote the reflections above ===\n\n")
            parts.append(cut(cursor, end_all))
            key = f"D-{name}-{chunk_start // CHUNK + 1:02d}"
            (out / f"{key}.md").write_text("# The reading\n\n" + "".join(parts) + "\n", encoding="utf-8")
            index.append({"packet": key, "reading": name, "analyse": [chunk_start + 1, chunk_end],
                          "thought_ids": [t for _, _, t in flat[chunk_start:chunk_end]]})
    (HERE / "development" / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    print(len(index), "packets")


if __name__ == "__main__":
    main()
