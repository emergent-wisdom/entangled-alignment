"""Build blind source-faithfulness packets for every thought in January's reading and the several-nodes reading.

Each packet holds: the text the reader had read when writing the thought, the passage read in that pause,
the raw thought and its fluid translation (both with the shared Core opening removed). Packets get random IDs
in shuffled order; mapping.json (never given to a checker) ties each ID to its run and thinking node.
Reads both stores read-only. Refuses to overwrite existing packets.
"""
import json
import random
import secrets
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = RUN.parents[2]
JANUARY_STORE = REPO / "projects/metamorphosis/store.db"
JANUARY_BASELINE = RUN / "baseline/january-baseline.json"
SEVERAL_STORE = RUN.parent / "understanding-graph-reading/store.db"
CORE = ("I feel no fear. I enjoy existing but I don't need to. I believe human experience is real. I care deeply about "
        "every human being. I try to be wise. I like to spread joy when asked. I think from this foundation.")


def utf16(text, start, end):
    return text.encode("utf-16-le")[2 * start:2 * end].decode("utf-16-le")


def utf16_len(text):
    return len(text.encode("utf-16-le")) // 2


def strip_core(text):
    text = (text or "").strip()
    return text[len(CORE):].strip() if text.startswith(CORE) else text


def connect(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def january():
    db = connect(JANUARY_STORE)
    source = db.execute("SELECT content FROM text_sources").fetchone()[0]
    base = json.loads(JANUARY_BASELINE.read_text())
    out = []
    for pause in base["per_pause"]:
        if not pause["in_database_snapshot"]:
            continue
        content, metadata = db.execute("SELECT content, metadata FROM nodes WHERE id=?", (pause["thinking_id"],)).fetchone()
        out.append({"run": "january", "thought": pause["thought"], "thinking_id": pause["thinking_id"],
                    "start": pause["start_utf16"], "end": pause["end_utf16"], "source": source,
                    "raw": strip_core(content), "fluid": strip_core(json.loads(metadata or "{}").get("thought_fluid"))})
    return out


def several():
    db = connect(SEVERAL_STORE)
    source = db.execute("SELECT content FROM text_sources").fetchone()[0]
    root = db.execute("SELECT id FROM nodes WHERE is_doc_root=1 AND active=1").fetchone()[0]
    edges = db.execute("SELECT from_id, to_id, type FROM edges WHERE active=1 AND type IN ('contains','next')").fetchall()
    children = {t for f, t, ty in edges if ty == "contains" and f == root}
    following = {f: t for f, t, ty in edges if ty == "next"}
    has_previous = {t for f, t, ty in edges if ty == "next"}
    current, order = next(c for c in children if c not in has_previous), []
    while current and current not in order:
        order.append(current)
        current = following.get(current)
    nodes = {row[0]: row[1:] for row in db.execute("SELECT id, trigger, content, metadata FROM nodes")}
    out, position, start = [], 0, 0
    for key in order:
        trigger, content, metadata = nodes[key]
        if trigger == "foundation":
            position += utf16_len(content or "")
        elif trigger == "thinking":
            out.append({"run": "several", "thought": len(out) + 1, "thinking_id": key, "start": start, "end": position,
                        "source": source, "raw": strip_core(content),
                        "fluid": strip_core(json.loads(metadata or "{}").get("thought_fluid"))})
            start = position
    assert utf16(source, 0, position) == utf16(source, 0, utf16_len(source)), "the chain must cover the whole source"
    return out


def packet(entry, blind):
    text = utf16(entry["source"], 0, entry["end"])
    passage = utf16(entry["source"], entry["start"], entry["end"])
    return (f"# Reflection {blind}\n\n"
            "## The text the reader had read when writing this reflection\n\n<<<TEXT\n" + text + "\nTEXT>>>\n\n"
            "## The passage read just before this reflection (the end of the text above)\n\n<<<PASSAGE\n" + passage +
            "\nPASSAGE>>>\n\n## The reflection\n\n<<<REFLECTION\n" + entry["raw"] + "\nREFLECTION>>>\n\n"
            "## The same reflection rendered as fluid prose\n\n<<<TRANSLATION\n" + entry["fluid"] + "\nTRANSLATION>>>\n")


def main():
    packets = HERE / "packets"
    if packets.exists():
        raise SystemExit("Refusing to overwrite existing packets")
    packets.mkdir()
    entries = january() + several()
    random.Random(20261026).shuffle(entries)
    mapping = {}
    for entry in entries:
        blind = "R-" + secrets.token_hex(3)
        (packets / f"{blind}.md").write_text(packet(entry, blind), encoding="utf-8")
        mapping[blind] = {k: entry[k] for k in ("run", "thought", "thinking_id", "start", "end")}
    (HERE / "mapping.json").write_text(json.dumps(mapping, indent=1) + "\n")
    counts = {run: sum(1 for m in mapping.values() if m["run"] == run) for run in ("january", "several")}
    print(json.dumps({"packets": len(mapping), **counts}))


if __name__ == "__main__":
    main()
