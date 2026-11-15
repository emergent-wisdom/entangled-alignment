#!/usr/bin/env python3
"""Take the text of the LLaDA paper out of the January LLaDA records, or put it back.

The records in projects/llada/store.db and chronological_metacognition/traces/llada/swarm.jsonl were made by
reading main.tex of arXiv:2502.09992v3. That paper is not ours to redistribute, so the released records carry a
marker wherever a passage of 150 characters or more of it stood:

    [[LLaDA paper text omitted: arXiv:2502.09992v3 main.tex, characters 2000-4000, esc 1]]

The two numbers are positions in main.tex, counted in characters from 0, the second one not included. "esc" says
how many times the passage was JSON-escaped where it stood (a tool result inside a trace record is escaped once).
Shorter quotations inside the agents' own notes are left as they were written.

    python llada_source_text.py check                       # do the records hold markers or text?
    python llada_source_text.py restore path/to/main.tex    # put the text back, exactly as recorded
    python llada_source_text.py strip path/to/main.tex      # replace it by markers again

Get main.tex from https://arxiv.org/e-print/2502.09992v3. After a restore the trace is byte for byte the recorded
one and every cell of the store's tables holds its recorded value; the store's search index is rebuilt.
"""
import argparse
import bisect
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORE = REPO / "projects/llada/store.db"
TRACE = REPO / "chronological_metacognition/traces/llada/swarm.jsonl"
SHA256 = "d42c3dfa9a7d478fa69567f9286d8117912a9a040a9d6a6b0914f50d47036a28"
MIN = 150       # shortest passage replaced, in characters of main.tex
SEED = 32
DEPTHS = (0, 1, 2)
MARK = "[[LLaDA paper text omitted: arXiv:2502.09992v3 main.tex, characters {}-{}, esc {}]]"
MARK_RE = re.compile(r"\[\[LLaDA paper text omitted: arXiv:2502\.09992v3 main\.tex, characters (\d+)-(\d+), esc (\d)\]\]")
COMPACT = {"separators": (",", ":"), "ensure_ascii": False}


def escaped(text, depth):
    for _ in range(depth):
        text = json.dumps(text, ensure_ascii=False)[1:-1]
    return text


class Source:
    def __init__(self, path):
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != SHA256:
            sys.exit(f"{path} is not main.tex of arXiv:2502.09992v3 (SHA-256 {SHA256})")
        self.text = data.decode("utf-8")
        self.forms = {}
        self.seeds = set()
        for depth in DEPTHS:
            pieces = {ch: escaped(ch, depth) for ch in set(self.text)}
            starts, at = [], 0
            for ch in self.text:
                starts.append(at)
                at += len(pieces[ch])
            starts.append(at)
            form = "".join(pieces[ch] for ch in self.text)
            index = {}
            for i in range(len(form) - SEED + 1):
                index.setdefault(form[i:i + SEED], []).append(i)
            self.forms[depth] = (form, starts, index)
            self.seeds.update(index)

    def strip(self, text):
        size = len(text)
        if size < MIN:
            return text
        out, last, i = [], 0, 0
        while i <= size - SEED:
            seed = text[i:i + SEED]
            if seed not in self.seeds:
                i += 1
                continue
            best = (0, 0, 0)
            for depth, (form, starts, index) in self.forms.items():
                for at in index.get(seed, ()):
                    length = SEED
                    while i + length < size and at + length < len(form) and text[i + length] == form[at + length]:
                        length += 1
                    if length > best[0]:
                        best = (length, depth, at)
            length, depth, at = best
            starts = self.forms[depth][1]
            first = bisect.bisect_left(starts, at)                  # whole characters of main.tex only
            end = bisect.bisect_right(starts, at + length) - 1
            if end - first >= MIN:
                out.append(text[last:i + starts[first] - at])
                out.append(MARK.format(first, end, depth))
                last = i = i + starts[end] - at
            else:
                i += 1
        if not out:
            return text
        out.append(text[last:])
        return "".join(out)

    def restore(self, text):
        return MARK_RE.sub(lambda m: escaped(self.text[int(m[1]):int(m[2])], int(m[3])), text)


def mapped(value, change):
    if isinstance(value, str):
        return change(value)
    if isinstance(value, list):
        return [mapped(item, change) for item in value]
    if isinstance(value, dict):
        return {key: mapped(item, change) for key, item in value.items()}
    return value


def text_cells(db):
    tables = [row[0] for row in db.execute(
        "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' and name not like 'nodes_fts%'")]
    for table in tables:
        for column in [row[1] for row in db.execute(f'pragma table_info("{table}")')]:
            query = f'select rowid, "{column}" from "{table}" where typeof("{column}") = \'text\''
            for rowid, value in db.execute(query).fetchall():
                yield table, column, rowid, value


def change_store(path, change):
    db = sqlite3.connect(path)
    changed = 0
    for table, column, rowid, value in text_cells(db):
        new = change(value)
        if new != value:
            db.execute(f'update "{table}" set "{column}" = ? where rowid = ?', (new, rowid))
            changed += 1
    db.commit()
    db.execute("vacuum")        # so that no replaced text stays in the file's free pages
    db.close()
    return changed


def change_trace(path, change):
    with open(path, encoding="utf-8", newline="") as handle:
        lines = handle.read().split("\n")
    changed = 0
    for number, line in enumerate(lines):
        if not line:
            continue
        record = json.loads(line)
        if json.dumps(record, **COMPACT) != line:
            sys.exit(f"{path}: line {number + 1} is not in the compact form this script writes; nothing was changed")
        new = json.dumps(mapped(record, change), **COMPACT)
        if new != line:
            lines[number] = new
            changed += 1
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines))
    return changed


def check(store, trace):
    db = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    in_store = sum(len(MARK_RE.findall(value)) for _, _, _, value in text_cells(db))
    with open(trace, encoding="utf-8", newline="") as handle:
        in_trace = len(MARK_RE.findall(handle.read()))
    print(f"{store}: {in_store} markers")
    print(f"{trace}: {in_trace} markers")
    print("The paper's text is replaced by markers." if in_store and in_trace else "The records hold the paper's text.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["check", "restore", "strip"])
    parser.add_argument("main_tex", nargs="?", help="main.tex of arXiv:2502.09992v3 (for restore and strip)")
    parser.add_argument("--store", default=STORE, type=Path)
    parser.add_argument("--trace", default=TRACE, type=Path)
    args = parser.parse_args()
    if args.command == "check":
        return check(args.store, args.trace)
    if not args.main_tex:
        parser.error(f"{args.command} needs the path to main.tex")
    source = Source(args.main_tex)
    change = source.strip if args.command == "strip" else source.restore
    print(f"{args.store}: {change_store(args.store, change)} cells changed")
    print(f"{args.trace}: {change_trace(args.trace, change)} records changed")


if __name__ == "__main__":
    main()
