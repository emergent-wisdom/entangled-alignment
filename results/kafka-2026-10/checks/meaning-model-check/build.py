"""Build source-faithfulness and read-ahead packets for the Meaning Model reading.

    python3 build.py <store.sqlite> <reads.json>

The same packet formats as the October checks: one thought packet per thinking block (checked with
../faithfulness-check/PROMPT.md) and record packets (checked with RECORD-PROMPT.md). Each packet gives the text read
when its contents were written.

- A thought think.rNN (and its translation.rNN) belongs to read NN. The build asserts that it was written after read
  NN entered the graph and before read NN+1 did. think.r42 was written after the last read, in the end pass; it gets
  the whole text.
- A model revision's horizon is the last read imported before it existed: read NN's import is bound to an earlier
  model, and read NN+1's import to this model or a later one. Records written after the last thought of read 40 form
  the end pass and are split into packets of moderate size.
- Record packets hold every model change of their window (all applied: this reading had no proposal cycle) and any
  graph note held by a character.

Reads the store read-only, and the paragraphs of each read from reads.json; refuses to overwrite packets.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parents[1] / "source/metamorphosis-johnston.txt").read_text(encoding="utf-8")
CORE = ("I feel no fear. I enjoy existing but I don't need to. I believe human experience is real. I care deeply about "
        "every human being. I try to be wise. I like to spread joy when asked. I think from this foundation.")
PACKETS = HERE / "packets"
LIMIT = 150_000  # characters of records per packet before splitting
MOST = 60  # records per packet: the October packets held a median of 46


def strip_core(text):
    text = (text or "").strip()
    assert text.startswith(CORE), text[:80]
    return text[len(CORE):].strip()


def block(name, body):
    return f"<<<{name}\n{body}\n{name}>>>"


def reads_in_source(path):
    """Start and end of each read in the source, from the whole paragraphs the reader was given."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", SOURCE)]
    paragraphs = [part for part in paragraphs if part]
    spans, at = {}, 0
    for read in json.loads(Path(path).read_text(encoding="utf-8"))["reads"]:
        number = read["read"]
        text = "\n\n".join(paragraphs[read["from"]:read["to"]])
        start = SOURCE.find(text, at)
        assert start >= 0 and SOURCE[at:start].strip() == "", f"read {number} is not contiguous in the source"
        spans[number] = (start, start + len(text))
        at = start + len(text)
    assert SOURCE[at:].strip() == "", "the reads do not reach the end of the source"
    return spans


def main(store, reads):
    spans = reads_in_source(reads)
    last_read = max(spans)
    db = sqlite3.connect(Path(store).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    base = dict(db.execute("select model_hash, base_model_hash from models"))
    depth = {}

    def chain(h):
        if h not in depth:
            depth[h] = 0 if not base.get(h) else chain(base[h]) + 1
        return depth[h]

    models = {chain(h): json.loads(blob) for h, blob in db.execute("select model_hash, definition_json from models")}
    revisions = [(n, json.loads(blob)) for n, blob in db.execute(
        "select revision_number, revision_json from narrative_revisions order by revision_number")]
    bound, imported, notes = {}, {}, {}
    for number, revision in revisions:
        source = revision.get("source") or {}
        bound[number] = chain(source["model_hash"]) if source.get("model_hash") in base else -1
        for operation in (revision.get("payload", {}).get("delta", {}) or {}).get("node_operations", []) or []:
            node = operation.get("node") or {}
            ident = node.get("id") or ""
            match = re.fullmatch(r"source\.r(\d{3})", ident)
            if match and int(match.group(1)) not in imported:
                imported[int(match.group(1))] = number
            notes.setdefault(ident, []).append((number, node))
    # Read 1 entered the graph only as a summary node, not as source.r001: it counts as read from the first revision,
    # before any model change.
    import_bound = {n: bound[r] for n, r in imported.items()}
    if 1 not in imported:
        imported[1], import_bound[1] = revisions[0][0], -1
    assert sorted(imported) == sorted(spans), (sorted(imported)[:5], len(imported), len(spans))

    def read_at(revision):
        """The last read imported at or before a graph revision."""
        return max((n for n, r in imported.items() if r <= revision), default=0)

    def unwrap(node):
        text = node.get("text") or ""
        try:
            inner = json.loads(text)
            return inner.get("text", text) if isinstance(inner, dict) else text
        except json.JSONDecodeError:
            return text

    # Thoughts and their translations.
    thoughts = []
    for ident, history in notes.items():
        match = re.fullmatch(r"think\.r(\d{2})([ab]?)", ident)
        if not match:
            continue
        (revision, node), = history  # each thought is written once
        read = int(match.group(1))
        translation = notes[f"translation.r{match.group(1)}{match.group(2)}"]
        (translated_at, translated), = translation
        if read <= last_read:
            assert imported[read] < revision, (ident, "written before its read was imported")
            if read < last_read:
                assert revision < imported[read + 1], (ident, "written after the next read was imported")
            pause, horizon = read, read
        else:
            assert revision > imported[last_read], ident
            pause, horizon = last_read + 1, last_read  # the end pass
        thoughts.append({"id": ident, "pause": pause, "horizon": horizon, "revision": revision,
                         "suffix": match.group(2), "text": strip_core(unwrap(node)),
                         "translation_id": f"translation.r{match.group(1)}{match.group(2)}",
                         "translation": strip_core(unwrap(translated)), "translated_at": translated_at})
    thoughts.sort(key=lambda t: (t["pause"], t["suffix"]))
    end_of_reading = max(t["revision"] for t in thoughts if t["pause"] == last_read)

    def head(horizon):
        start, end = spans[horizon]
        return ["## The text the reader had read", block("TEXT", SOURCE[:end]),
                "## The passage read just before (the end of the text above)", block("PASSAGE", SOURCE[start:end])]

    PACKETS.mkdir(exist_ok=True)
    index = []
    numbered = {}
    for thought in thoughts:
        number = numbered[thought["pause"]] = numbered.get(thought["pause"], 0) + 1
        key = f"T-{thought['pause']:02d}-{number}"
        parts = head(thought["horizon"])
        text = "\n\n".join([f"# Reflection {key}", *parts[:2],
                            "## The passage read just before this reflection (the end of the text above)", parts[3],
                            "## The reflection", block("REFLECTION", thought["text"]),
                            "## The same reflection rendered as fluid prose", block("TRANSLATION", thought["translation"])])
        assert not (PACKETS / f"{key}.md").exists(), key
        (PACKETS / f"{key}.md").write_text(text + "\n")
        index.append({"packet": key, "pause": thought["pause"], "kind": "thought", "thinking_id": thought["id"],
                      "translation_id": thought["translation_id"], "horizon_read": thought["horizon"],
                      "graph_revision": thought["revision"]})

    # Model revisions: horizon from the binding of each read's import; when, from the first graph revision bound to it.
    def horizon_of(d):
        return max((n for n, b in import_bound.items() if b < d), default=0)

    def first_bound(d):
        return min((r for r, b in bound.items() if b >= d), default=max(bound))

    windows = {}
    for d in sorted(models):
        if d == 0:
            continue  # the scaffold the server creates before any reading; it holds no claim about the story
        horizon = horizon_of(d)
        if horizon == 0:
            horizon = 1  # written while read 1 was being taken in, before its graph import; checked against read 1
        pause = horizon if (horizon < last_read or first_bound(d) <= end_of_reading) else last_read + 1
        for change in models[d].get("changes", []):
            path = ".".join(str(p) for p in change.get("path", []))
            items = change.get("upsert") or []
            if items:
                for item in items:
                    ident = item.get("id") or item.get("event_id") or item.get("processId") or "?"
                    windows.setdefault((pause, horizon), []).append(
                        {"id": f"{path}:{ident}", "type": "model change", "status": "applied", "model_revision": d,
                         "record": item})
            else:
                windows.setdefault((pause, horizon), []).append(
                    {"id": f"{change.get('op')}:{path}", "type": "model change", "status": "applied",
                     "model_revision": d, "change": change})
    # Graph notes held by a character, not the Reader.
    for ident, history in notes.items():
        for revision, node in history:
            holder = node.get("holder")
            if holder and holder != "Reader":
                read = read_at(revision)
                pause = read if (read < last_read or revision <= end_of_reading) else last_read + 1
                windows.setdefault((pause, read), []).append(
                    {"id": ident, "type": "character thought", "status": "applied", "holder": holder,
                     "graph_revision": revision, "text": unwrap(node), "value_time": node.get("value_time")})

    for (pause, horizon), items in sorted(windows.items()):
        parts, current, size = [], [], 0
        for item in items:
            length = len(json.dumps(item, ensure_ascii=False))
            if current and (size + length > LIMIT or len(current) >= MOST):
                parts.append(current)
                current, size = [], 0
            current.append(item)
            size += length
        if current:
            parts.append(current)
        for number, part in enumerate(parts, 1):
            key = f"R-{pause:02d}" + (f"-{number}" if len(parts) > 1 else "")
            text = "\n\n".join([f"# Records of pause {pause}" + (f", part {number} of {len(parts)}" if len(parts) > 1 else ""),
                                *head(horizon), "## The records",
                                block("RECORDS", json.dumps(part, indent=1, ensure_ascii=False))])
            assert not (PACKETS / f"{key}.md").exists(), key
            (PACKETS / f"{key}.md").write_text(text + "\n")
            index.append({"packet": key, "pause": pause, "kind": "records", "items": len(part), "horizon_read": horizon,
                          "model_revisions": sorted({i.get("model_revision") for i in part if i.get("model_revision")})})
    (HERE / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    kinds = {}
    for item in index:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    print(json.dumps({"reads": len(spans), "thoughts": len(thoughts), "packets": kinds,
                      "records": sum(i.get("items", 0) for i in index),
                      "end_pass_packets": sum(1 for i in index if i["pause"] == last_read + 1)}))


if __name__ == "__main__":
    main(*sys.argv[1:])
