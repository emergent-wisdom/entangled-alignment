"""Extract the Kafka readings into one shape, for the development analyses.

    python3 extract.py

Writes traces.json: for each reading, its pauses (positions as a fraction of the story), every record with the pause
that created it and its layer, and every link between records. Reads the stores and state read-only.

Layers:
- "thought": the Synthesizer's Core-prefixed thought (Core removed here); "translation": its prose rendering;
- "graph": every other record the reading wrote (Workers' and the Synthesizer's own nodes, notes or model records);
- "character": a thought the Meaning Model holds for a character.
Positions: the Johnston text has no front matter, so a fraction is position / 122,332. January's Wyllie text runs
from its first story sentence (999) to the Gutenberg end marker (121,283); positions are taken relative to that span.
"""
import json
import gzip
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = RUN.parents[2]
CORE = ("I feel no fear. I enjoy existing but I don't need to. I believe human experience is real. I care deeply about "
        "every human being. I try to be wise. I like to spread joy when asked. I think from this foundation.")


def strip_core(text):
    text = (text or "").strip()
    return text[len(CORE):].strip() if text.startswith(CORE) else text


def connect(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def words(text):
    return len(re.findall(r"\w+", text or ""))


def january():
    db = connect(REPO / "projects/metamorphosis/store.db")
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())
    first, last = base["source_boundaries_utf16"]["story_first_sentence"], base["source_boundaries_utf16"]["gutenberg_end_marker"]
    frac = lambda pos: max(0.0, min(1.0, (pos - first) / (last - first)))
    nodes = {r[0]: r[1:] for r in db.execute("SELECT id, trigger, title, content, understanding, metadata, created_at FROM nodes")}
    pauses, records = [], {}
    for p in base["per_pause"]:
        if not p["in_database_snapshot"]:
            continue
        number = len(pauses) + 1
        tid = p["thinking_id"]
        trigger, title, content, understanding, metadata, created = nodes[tid]
        pauses.append({"pause": number, "start": frac(p["start_utf16"]), "end": frac(p["end_utf16"]),
                       "start_raw": p["start_utf16"], "end_raw": p["end_utf16"], "thoughts": [tid]})
        records[tid] = {"pause": number, "layer": "thought", "role": "synthesizer", "kind": "thinking", "title": title,
                        "text": strip_core(content)}
        fluid = json.loads(metadata or "{}").get("thought_fluid")
        records[tid + ":fluid"] = {"pause": number, "layer": "translation", "role": "translator", "kind": "translation",
                                   "title": title, "text": strip_core(fluid)}
        for cid in p["concept_ids"]:
            if cid in nodes:
                trigger, title, content, understanding, metadata, created = nodes[cid]
                records[cid] = {"pause": number, "layer": "graph", "role": (p["concept_creators"] and None), "kind": trigger,
                                "title": title, "text": understanding or content or ""}
    links = [{"from": f, "to": t, "type": ty, "why": ex or why or ""}
             for f, t, ty, ex, why in db.execute("SELECT from_id, to_id, type, explanation, why FROM edges WHERE active=1")
             if ty not in ("next", "contains")]
    return {"pauses": pauses, "records": records, "links": links, "story_chars": last - first}


def several():
    path = RUN.parent / "understanding-graph-reading/store.db"
    db = connect(path)
    source = db.execute("SELECT content FROM text_sources").fetchone()[0]
    total = len(source)
    root = db.execute("SELECT id FROM nodes WHERE is_doc_root=1 AND active=1").fetchone()[0]
    edges = db.execute("SELECT from_id, to_id, type FROM edges WHERE active=1 AND type IN ('contains','next')").fetchall()
    children = {t for f, t, ty in edges if ty == "contains" and f == root}
    following = {f: t for f, t, ty in edges if ty == "next"}
    has_previous = {t for f, t, ty in edges if ty == "next"}
    current, order = next(c for c in children if c not in has_previous), []
    while current and current not in order:
        order.append(current)
        current = following.get(current)
    nodes = {r[0]: r[1:] for r in db.execute("SELECT id, trigger, title, content, understanding, metadata, created_at, active FROM nodes")}
    pauses, records, position, start = [], {}, 0, 0
    for key in order:
        trigger, title, content, understanding, metadata, created, active = nodes[key]
        if trigger == "foundation":
            records[key] = {"pause": len(pauses) + 1, "layer": "source", "start": position / total,
                            "end": (position + len(content or "")) / total}
            position += len(content or "")
        elif trigger == "thinking":
            number = len(pauses) + 1
            pauses.append({"pause": number, "start": start / total, "end": position / total, "start_raw": start,
                           "end_raw": position, "thoughts": [key], "created": created})
            records[key] = {"pause": number, "layer": "thought", "role": "synthesizer", "kind": "thinking", "title": title,
                            "text": strip_core(content)}
            records[key + ":fluid"] = {"pause": number, "layer": "translation", "role": "translator", "kind": "translation",
                                       "title": title, "text": strip_core(json.loads(metadata or "{}").get("thought_fluid"))}
            start = position
    # Every other node belongs to the pause whose thought is the first one created at or after it.
    ends = [(p["created"], p["pause"]) for p in pauses]
    for key, (trigger, title, content, understanding, metadata, created, active) in nodes.items():
        if key in records or trigger in ("thinking", "foundation") or key == root or not active:
            continue
        pause = next((n for c, n in ends if created <= c), pauses[-1]["pause"])
        records[key] = {"pause": pause, "layer": "graph", "role": None, "kind": trigger, "title": title,
                        "text": understanding or content or ""}
    links = [{"from": f, "to": t, "type": ty, "why": ex or why or ""}
             for f, t, ty, ex, why in db.execute("SELECT from_id, to_id, type, explanation, why FROM edges WHERE active=1")
             if ty not in ("next", "contains")]
    for p in pauses:
        p.pop("created")
    return {"pauses": pauses, "records": records, "links": links, "story_chars": total}


def main():
    out = {"january": january(), "understanding-graph": several()}
    for name, reading in out.items():
        layers = {}
        for r in reading["records"].values():
            layers[r["layer"]] = layers.get(r["layer"], 0) + 1
        thought_words = sum(words(r["text"]) for r in reading["records"].values() if r["layer"] == "thought")
        print(name, len(reading["pauses"]), "pauses", layers, len(reading["links"]), "links", thought_words, "thought words")
    (HERE / "traces.json").write_text(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
