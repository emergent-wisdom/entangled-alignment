"""Build the outcome packets: every reader-held prediction or hypothesis record, with the whole story.

    python3 build_outcomes.py

Records are the graph-layer records whose kind is prediction or hypothesis (traces.json); the Meaning Model's
characters' own expectations are left out. Each packet has the story the reading read (Wyllie for January, Johnston
for the later readings) and up to 20 records, each with its position and the last words read. Record ids are
replaced by short labels (E-01 ...); outcomes/index.json maps them back.
"""
import json
from pathlib import Path

from build_development import stories, utf16

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
BATCH = 20


def main():
    traces = json.loads((HERE / "traces.json").read_text())
    wyllie, johnston = stories()
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())["source_boundaries_utf16"]
    first, last = base["story_first_sentence"], base["gutenberg_end_marker"]
    out = HERE / "outcomes" / "packets"
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for name, reading in traces.items():
        story = utf16(wyllie, first, last) if name == "january" else johnston
        offset = first if name == "january" else 0
        pauses = {p["pause"]: p for p in reading["pauses"]}
        records = sorted(((k, r) for k, r in reading["records"].items()
                          if r["layer"] == "graph" and r.get("kind") in ("prediction", "hypothesis")),
                         key=lambda kv: (kv[1]["pause"], kv[0]))
        for batch_start in range(0, len(records), BATCH):
            lines = []
            for number, (key, record) in enumerate(records[batch_start:batch_start + BATCH], batch_start + 1):
                pause = pauses[record["pause"]]
                end = max(pause["end_raw"] - offset, 0)
                tail = " ".join(story[:end].split()[-25:])
                label = f"E-{number:02d}"
                index[f"{name}:{label}"] = {"reading": name, "id": key, "pause": record["pause"], "end": pause["end"]}
                lines.append(f"### {label}\nWritten after reading {100 * pause['end']:.1f}% of the story. The last words read: "
                             f"\"…{tail}\"\nKind: {record['kind']}\nTitle: {record.get('title') or ''}\n"
                             f"Text: {record.get('text') or ''}\n")
            key = f"O-{name}-{batch_start // BATCH + 1}"
            (out / f"{key}.md").write_text("# The story\n\n<<<STORY\n" + story + "\nSTORY>>>\n\n# The records\n\n" +
                                           "\n".join(lines), encoding="utf-8")
    (HERE / "outcomes" / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    print(len(index), "records")


if __name__ == "__main__":
    main()
