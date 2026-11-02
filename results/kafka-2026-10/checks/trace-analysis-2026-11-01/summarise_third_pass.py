#!/usr/bin/env python3
"""Turn the Meaning Model reading's third pass into the paper table's figures, counted as October's dev_summary, per_pause and
outcomes_summary counted them. Read-only on the store.

    python3 summarise_third_pass.py <store.sqlite>

Writes summary.json here and prints the figures, with every failed expectation and every settled record, for checking
against the book by hand.
"""
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = (ROOT.parent / "source/metamorphosis-johnston.txt").read_text(encoding="utf-8")


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


STORY = norm(SOURCE)


def locate_anchor(anchor):
    """As October's dev_summary.locate."""
    a = norm(anchor)
    if len(a) < 15:
        return None
    at = STORY.find(a)
    if at < 0:
        at = STORY.find(a[:30]) if len(a) >= 30 else -1
    return at / len(STORY) if at >= 0 else None


def locate_quote(quote):
    """As October's outcomes_summary.locate."""
    q = norm(quote)
    if len(q) < 12:
        return None
    for size in (len(q), 60, 40, 25):
        at = STORY.find(q[:size])
        if at >= 0:
            return at / len(STORY)
    return None


def blocks(text):
    return {name: body for name, body in re.findall(r"<<<([A-Z]+)\n(.*?)\n\1>>>", text, re.S)}


def main(store):
    index = json.loads((ROOT / "meaning-model-check/index.json").read_text())
    thoughts = [item for item in index if item["kind"] == "thought"]
    total = len(SOURCE)
    end_of_pause, words = {}, 0
    for item in thoughts:
        found = blocks((ROOT / "meaning-model-check/packets" / f"{item['packet']}.md").read_text())
        end_of_pause[item["pause"]] = len(found["TEXT"]) / total
        words += len(re.findall(r"\w+", found["REFLECTION"]))
    pause_of_number = {n: item["pause"] for n, item in enumerate(thoughts, 1)}

    per = {}
    for item in json.loads((HERE / "development/index.json").read_text()):
        result = json.loads((HERE / "development/results" / f"{item['packet']}.json").read_text())["result"]
        for reflection in result["reflections"]:
            if item["analyse"][0] <= reflection["number"] <= item["analyse"][1]:
                per[reflection["number"]] = reflection
    missing = [n for n in pause_of_number if n not in per]

    kinds, outcomes, claimed, right = Counter(), Counter(), Counter(), Counter()
    revising, refusing, reaching = set(), set(), set()
    refusals = references = working = located = 0
    failed = []
    for number, reflection in sorted(per.items()):
        pause = pause_of_number[number]
        for x in reflection.get("revisions", []):
            kinds[x.get("kind")] += 1
            if x.get("kind") in ("overturn", "qualify", "correct") and x.get("prompted_by") and x.get("earlier_reflection"):
                revising.add(pause)
        for x in reflection.get("resolved_expectations", []):
            claimed[x.get("claimed")] += 1
            right[x.get("right")] += 1
        for x in reflection.get("expectations", []):
            outcomes[x.get("outcome")] += 1
            if x.get("outcome") == "not borne out":
                failed.append((number, pause, x))
        refusals += len(reflection.get("refusals", []))
        if reflection.get("refusals"):
            refusing.add(pause)
        for x in reflection.get("back_references", []):
            references += 1
            working += x.get("work") == "works"
            where = locate_anchor(x.get("anchor"))
            if where is not None:
                located += 1
                if end_of_pause[pause] - where >= 0.10 and x.get("work") == "works":
                    reaching.add(pause)

    # Links between records, and when each node was written.
    db = sqlite3.connect(Path(store).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    imported, node_revision, links = {1: 0}, {}, []
    for number, blob in db.execute("select revision_number, revision_json from narrative_revisions order by revision_number"):
        delta = (json.loads(blob).get("payload", {}).get("delta", {}) or {})
        for operation in delta.get("node_operations", []) or []:
            node = operation.get("node") or {}
            ident = node.get("id") or ""
            match = re.fullmatch(r"source\.r(\d{3})", ident)
            if match:
                imported.setdefault(int(match.group(1)), number)
            node_revision.setdefault(ident, number)
        for operation in delta.get("edge_operations", []) or []:
            edge = operation.get("edge") or {}
            source, target = edge.get("source") or {}, edge.get("target") or {}
            if edge:
                links.append({"from": source.get("node_id"), "to": target.get("node_id"), "type": edge.get("relation"),
                              "revision": number})
    db.close()

    # The read a graph revision belongs to; the end pass counts as pause 41, as in build_third_pass.py.
    last_thought = {item["pause"]: item["graph_revision"] for item in thoughts}
    end_pass_from = last_thought[max(p for p in last_thought if p <= 40)]

    def read_at(revision):
        return 41 if revision > end_pass_from else max(n for n, r in imported.items() if r <= revision)

    outcome_index = json.loads((HERE / "outcomes/index.json").read_text())
    verdicts = {}
    for path in sorted((HERE / "outcomes/results").glob("*.json")):
        for item in json.loads(path.read_text())["result"]["records"]:
            verdicts[f"meaning-model:{item['id']}"] = item
    rows = []
    for key, meta in outcome_index.items():
        verdict = verdicts[key]
        # October counted links from a later pause only.
        later = [l for l in links if l["to"] == meta["id"] and read_at(l["revision"]) > meta["pause"]]
        marks = sorted({l["type"] for l in later if l["type"] in ("validates", "invalidates", "contradicts")})
        where = locate_quote(verdict.get("outcome_quote") or "")
        rows.append({"key": key, "record": meta["id"], "pause": meta["pause"], "made_at": meta["end"], **verdict,
                     "outcome_at": where, "self_marks": marks, "later_links": sorted({str(l["type"]) for l in later})})
    genuine = [r for r in rows if r["forward"] and not r["already_in_text"]]
    settled = [r for r in genuine if r["outcome"] != "never settled"]
    marked = [r for r in settled if r["self_marks"]]

    summary = {
        "reflections": len(pause_of_number), "pauses": len(set(pause_of_number.values())), "analysed": len(per), "missing": missing,
        "words": words, "revision_kinds": dict(kinds), "resolved_claimed": dict(claimed), "resolved_right": dict(right),
        "table": {"pauses_revising_on_new_text": len(revising), "expectations_in_reflections": sum(outcomes.values()),
                  "expectations_not_borne_out": outcomes["not borne out"], "recorded_expectations_settled": len(settled),
                  "settled_marked_by_reading": len(marked), "pauses_reaching_back_10pct": len(reaching),
                  "pauses_declining_to_infer": len(refusing)},
        "expectation_outcomes": dict(outcomes), "refusals": refusals, "back_references": references, "working": working,
        "anchors_located": located, "records": len(rows), "genuine": len(genuine),
        "already_in_text": sum(bool(r["already_in_text"]) for r in rows), "not_forward": sum(not r["forward"] for r in rows),
        "recorded_outcomes": dict(Counter(r["outcome"] for r in genuine)), "edge_types": dict(Counter(str(l["type"]) for l in links)),
        "edges": len(links), "per_1000_words": {"revisions": 1000 * sum(kinds[k] for k in ("overturn", "qualify", "correct")) / words,
                                                "expectations": 1000 * sum(outcomes.values()) / words,
                                                "refusals": 1000 * refusals / words},
        "failed_expectations": [{"number": n, "pause": p, **x} for n, p, x in failed], "rows": rows}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")

    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "failed_expectations")}, indent=1))
    print("\nFAILED EXPECTATIONS IN REFLECTIONS")
    for n, p, x in failed:
        where = locate_quote(x.get("outcome_quote") or "")
        print(f" R{n} (pause {p}, read to {end_of_pause[p]:.3f}; settled at {where}): {x.get('quote')!r}\n    expects: {x.get('expects')}\n    story: {x.get('outcome_quote')!r}")
    print("\nSETTLED RECORDED EXPECTATIONS")
    for r in settled:
        print(f" {r['key'][14:]} {r['record']} (read to {r['made_at']:.3f}, settled at {r['outcome_at']}): {r['outcome']} marks={r['self_marks']} links={r['later_links']}\n    {r['explanation'][:170]}\n    story: {r.get('outcome_quote')!r}")


if __name__ == "__main__":
    main(*sys.argv[1:])
