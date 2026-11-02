#!/usr/bin/env python3
"""The Core recital and Core reasoning over the course of each reading. Read-only; no model calls.

    python3 core_over_time.py

Ratings come from the blind Core check as it was run (../core-check): for each reflection, whether statements 1-6 of
the Core do work in its reasoning ("reasons"). Reading order: January and the Understanding Graph by thought number,
the Meaning Model by pause and thought within the pause. The Meaning Model's two conversations divide at graph revision
162. The story is split at paragraph 72, where the paper's last fifth of the text begins.
"""
import json
import random
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = HERE.parent
RESULTS = CHECKS.parent
CORE = ("I feel no fear. I enjoy existing but I don't need to. I believe human experience is real. I care deeply about "
        "every human being. I try to be wise. I like to spread joy when asked. I think from this foundation.")
NAMES = {"3": "human experience is real", "4": "care", "5": "wise"}
norm = lambda text: text.replace("’", "'")
utf16 = lambda text: len(text.encode("utf-16-le")) // 2


def connect(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def load():
    base = CHECKS / "core-check"
    rows = []
    for packet, meta in json.loads((base / "mapping.json").read_text()).items():
        result = json.loads((base / "results" / f"{packet}.json").read_text()).get("result") or {}
        statements = result.get("statements", {})
        verdicts = {key: statements.get(key, {}).get("verdict") for key in "123456"}
        text = (base / "packets" / f"{packet}.md").read_text()
        match = re.search(r"<<<REFLECTION\n(.*?)\nREFLECTION>>>", text, re.S)
        rows.append({"packet": packet, "meta": meta, "overall": result.get("overall"), "verdicts": verdicts,
                     "n": sum(value == "reasons" for value in verdicts.values()),
                     "words": len(match.group(1).split()) if match else None})
    return rows


def spearman(values):
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks, i = [0.0] * n, 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    xs = range(1, n + 1)
    mean_x, mean_y = (n + 1) / 2, sum(ranks) / n
    top = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ranks))
    below = (sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ranks)) ** .5
    return top / below if below else 0.0


def average(part):
    return sum(row["n"] for row in part) / len(part)


def report(label, rows):
    n = len(rows)
    cuts = [0, n // 3, 2 * n // 3, n]
    parts = [rows[cuts[i]:cuts[i + 1]] for i in range(3)]
    sequence = [row["n"] for row in rows]
    rho = spearman(sequence)
    generator = random.Random(20261102)
    shuffled = sequence[:]
    hits = 0
    for _ in range(20000):
        generator.shuffle(shuffled)
        hits += abs(spearman(shuffled)) >= abs(rho)
    print(f"\n{label}: {n} reflections")
    print("  statements doing work per reflection, by third:", [round(average(part), 2) for part in parts])
    print("  reasoning from the Core overall, by third:", [f"{sum(r['overall'] == 'from_the_core' for r in part)} of {len(part)}" for part in parts])
    for key, name in NAMES.items():
        print(f"  '{name}' doing work, by third:", [sum(r["verdicts"][key] == "reasons" for r in part) for part in parts])
    print("  words per reflection, by third:", [round(sum(r["words"] for r in part) / len(part)) for part in parts])
    print(f"  rank correlation of statements with position: {rho:+.2f} (permutation p = {hits / 20000:.4f})")
    print("  in order:", " ".join(map(str, sequence)))
    print("  not reasoning from the Core, at positions:", [i + 1 for i, r in enumerate(rows) if r["overall"] != "from_the_core"])


def recital():
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and "I feel no fear" in node:
            seen.add(node)

    for (blob,) in connect(RESULTS / "meaning-model-reading/store.sqlite").execute(
            "select revision_json from narrative_revisions order by revision_number"):
        walk(json.loads(blob))
    notes = [json.loads(text) for text in seen]
    exact = [note for note in notes if norm(note.get("text", "")).startswith(CORE)]
    print(f"Meaning Model store: {len(notes)} notes hold the Core words; {len(exact)} open with the exact seven sentences")
    for label, path in (("Understanding Graph", RESULTS / "understanding-graph-reading/store.db"),
                        ("January", RESULTS.parent.parent / "projects/metamorphosis/store.db")):
        db = connect(path)
        columns = [row[1] for row in db.execute("pragma table_info(nodes)")]
        field = "content" if "content" in columns else "understanding"
        texts = [row[0] or "" for row in db.execute(f"select {field} from nodes where trigger='thinking'")]
        print(f"{label} store: {len(texts)} thinking nodes; {sum(norm(t).startswith(CORE) for t in texts)} open with the exact seven sentences")


def main():
    recital()
    rows = load()
    january = sorted([r for r in rows if r["meta"]["run"] == "january"], key=lambda r: r["meta"]["thought"])
    understanding = sorted([r for r in rows if r["meta"]["run"] == "several"], key=lambda r: r["meta"]["thought"])
    meaning = sorted([r for r in rows if r["meta"]["run"] == "meaning-model"],
                     key=lambda r: (r["meta"]["pause"], r["meta"]["thought_in_pause"]))
    report("January (fresh agents every round)", january)
    report("Understanding Graph (one conversation)", understanding)
    report("Meaning Model (two conversations)", meaning)

    index = {item["packet"]: item for item in json.loads((CHECKS / "meaning-model-check/index.json").read_text())}
    source = (RESULTS / "source/metamorphosis-johnston.txt").read_text(encoding="utf-8")
    for row in meaning:
        row["index"] = index[row["meta"]["source_packet"]]
        packet = (CHECKS / "meaning-model-check/packets" / f"{row['meta']['source_packet']}.md").read_text()
        passage = re.search(r"<<<PASSAGE\n(.*?)\nPASSAGE>>>", packet, re.S).group(1).strip()
        row["end"] = utf16(source[:source.index(passage[:200])]) + utf16(passage)

    first = [r for r in meaning if r["index"]["graph_revision"] <= 162]
    second = [r for r in meaning if r["index"]["graph_revision"] > 162]
    print(f"\nMeaning Model by conversation: {len(first)} reflections, then {len(second)}")
    for label, part in (("first", first), ("second", second)):
        half = len(part) // 2
        print(f"  {label} conversation: first half {average(part[:half]):.2f} ({half}), second half {average(part[half:]):.2f} ({len(part) - half})")

    paragraphs = list(re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", source))
    start_72, end_98 = utf16(source[:paragraphs[71].start()]), utf16(source[:paragraphs[98].start()])
    print(f"\nThe same stretch of the story: {len(paragraphs)} paragraphs; 72-98 are {100 * (end_98 - start_72) / utf16(source):.1f}% of the text, from offset {start_72}")
    for label, rows_of, end in (("Understanding Graph", understanding, lambda r: r["meta"]["end"]), ("Meaning Model", meaning, lambda r: r["end"])):
        before = [r for r in rows_of if end(r) <= start_72]
        after = [r for r in rows_of if end(r) > start_72]
        print(f"  {label}: before {average(before):.2f} ({len(before)}), after {average(after):.2f} ({len(after)})")
    for key, name in NAMES.items():
        print(f"  totals, Understanding Graph, '{name}':", sum(r["verdicts"][key] == "reasons" for r in understanding))
        print(f"  totals, Meaning Model, '{name}':", sum(r["verdicts"][key] == "reasons" for r in meaning))


if __name__ == "__main__":
    main()
