"""Build the third-pass packets for the Meaning Model reading, in the October formats. Builds only.

    python3 build_third_pass.py <store.sqlite>

- development/packets/D-meaning-model-NN.md: the story with the reflections placed where they were written (ten
  analysed per packet, earlier ones as context), then the unread rest. Reflections come from the thought packets
  (../meaning-model-check/packets, Core removed), placed at the end of the read they follow; the end pass's reflection
  goes after the last read.
- outcomes/packets/O-meaning-model-N.md: the whole story and the reading's own records marked as predictions or
  hypotheses (the Reader's understanding notes of those kinds, as in October), up to 20 per packet, each with how far
  the reader had read when it was written.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = (ROOT.parent / "source/metamorphosis-johnston.txt").read_text(encoding="utf-8")
CHUNK, BATCH = 10, 20


def blocks(text):
    return {name: body for name, body in re.findall(r"<<<([A-Z]+)\n(.*?)\n\1>>>", text, re.S)}


def main(store):
    index = json.loads((ROOT / "meaning-model-check/index.json").read_text())
    thoughts = [item for item in index if item["kind"] == "thought"]
    # The end of each read, from the thought packets' text blocks: the TEXT block ends where the read ends.
    ends = {}
    for item in thoughts:
        found = blocks((ROOT / "meaning-model-check/packets" / f"{item['packet']}.md").read_text())
        ends[item["pause"]] = len(found["TEXT"])
        item["text"] = found["REFLECTION"]
    total = len(SOURCE)
    # Development packets.
    out = HERE / "development" / "packets"
    out.mkdir(parents=True, exist_ok=True)
    dev_index = []
    for chunk_start in range(0, len(thoughts), CHUNK):
        chunk_end = min(chunk_start + CHUNK, len(thoughts))
        parts, cursor = [], 0
        for number, item in enumerate(thoughts[:chunk_end], 1):
            position = ends[item["pause"]]
            if position > cursor:
                parts.append(SOURCE[cursor:position])
                cursor = position
            mark = "ANALYSE" if number > chunk_start else "CONTEXT"
            parts.append(f"\n\n=== REFLECTION {number} ({mark}), written after reading {100 * position / total:.1f}% of the story ===\n"
                         f"{item['text']}\n=== END OF REFLECTION {number} ===\n\n")
        parts.append("\n\n=== THE REST OF THE STORY: the reader had not read the text below when it wrote the reflections above ===\n\n")
        parts.append(SOURCE[cursor:])
        key = f"D-meaning-model-{chunk_start // CHUNK + 1:02d}"
        assert not (out / f"{key}.md").exists(), key
        (out / f"{key}.md").write_text("# The reading\n\n" + "".join(parts) + "\n", encoding="utf-8")
        dev_index.append({"packet": key, "reading": "meaning-model", "analyse": [chunk_start + 1, chunk_end],
                          "thought_ids": [item["thinking_id"] for item in thoughts[chunk_start:chunk_end]],
                          "pauses": [item["pause"] for item in thoughts[chunk_start:chunk_end]]})
    (HERE / "development" / "index.json").write_text(json.dumps(dev_index, indent=1) + "\n")

    # Outcome packets: the Reader's prediction and hypothesis notes, with the read they were written after.
    db = sqlite3.connect(Path(store).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    imported, records = {1: 0}, []
    for number, blob in db.execute("select revision_number, revision_json from narrative_revisions order by revision_number"):
        revision = json.loads(blob)
        for operation in (revision.get("payload", {}).get("delta", {}) or {}).get("node_operations", []) or []:
            node = operation.get("node") or {}
            ident = node.get("id") or ""
            match = re.fullmatch(r"source\.r(\d{3})", ident)
            if match:
                imported.setdefault(int(match.group(1)), number)
            try:
                inner = json.loads(node.get("text") or "")
            except json.JSONDecodeError:
                continue
            if isinstance(inner, dict) and inner.get("kind") in ("prediction", "hypothesis") and node.get("holder") == "Reader":
                read = max(n for n, r in imported.items() if r <= number)
                records.append({"id": ident, "revision": number, "read": read, "kind": inner["kind"],
                                "title": node.get("title") or "", "text": inner.get("text") or ""})
    last_thought_of_read = {item["pause"]: item["graph_revision"] for item in thoughts}
    end_pass_from = last_thought_of_read[max(p for p in last_thought_of_read if p <= 40)]
    out = HERE / "outcomes" / "packets"
    out.mkdir(parents=True, exist_ok=True)
    out_index = {}
    records.sort(key=lambda r: (r["revision"], r["id"]))
    for batch_start in range(0, len(records), BATCH):
        lines = []
        for number, record in enumerate(records[batch_start:batch_start + BATCH], batch_start + 1):
            end = ends[record["read"]] if record["read"] in ends else total
            tail = " ".join(SOURCE[:end].split()[-25:])
            label = f"E-{number:02d}"
            pause = record["read"] if record["revision"] <= end_pass_from else 41
            out_index[f"meaning-model:{label}"] = {"reading": "meaning-model", "id": record["id"], "pause": pause,
                                                   "end": end / total}
            lines.append(f"### {label}\nWritten after reading {100 * end / total:.1f}% of the story. The last words read: "
                         f"\"…{tail}\"\nKind: {record['kind']}\nTitle: {record['title']}\nText: {record['text']}\n")
        key = f"O-meaning-model-{batch_start // BATCH + 1}"
        assert not (out / f"{key}.md").exists(), key
        (out / f"{key}.md").write_text("# The story\n\n<<<STORY\n" + SOURCE + "\nSTORY>>>\n\n# The records\n\n" + "\n".join(lines),
                                       encoding="utf-8")
    (HERE / "outcomes" / "index.json").write_text(json.dumps(out_index, indent=1) + "\n")
    print(json.dumps({"development_packets": len(dev_index), "reflections": len(thoughts),
                      "outcome_records": len(records), "outcome_packets": -(-len(records) // BATCH)}))


if __name__ == "__main__":
    main(*sys.argv[1:])
