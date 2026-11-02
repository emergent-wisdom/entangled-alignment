"""Summarise the blind outcome check (outcomes/results) against each reading's own resolution links.

    python3 outcomes_summary.py

For every reader-held prediction or hypothesis record: the checker's verdicts, where in the story its outcome quote
falls (located by exact or whitespace-normalised search), whether the reading itself later marked it validated,
invalidated or contradicted, and whether any later record or thought names it in its text or links to it. Writes
outcomes/summary.json.
"""
import json
import re
import statistics
from pathlib import Path

from build_development import stories, utf16

HERE = Path(__file__).resolve().parent
RUN = HERE.parent


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def locate(quote, story_norm, total):
    q = norm(quote)
    if len(q) < 12:
        return None
    for size in (len(q), 60, 40, 25):
        piece = q[:size]
        at = story_norm.find(piece)
        if at >= 0:
            return at / total
    return None


def main():
    traces = json.loads((HERE / "traces.json").read_text())
    index = json.loads((HERE / "outcomes/index.json").read_text())
    wyllie, johnston = stories()
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())["source_boundaries_utf16"]
    texts = {"january": norm(utf16(wyllie, base["story_first_sentence"], base["gutenberg_end_marker"])),
             "understanding-graph": norm(johnston), "meaning-model": norm(johnston)}
    results = {}
    for path in sorted((HERE / "outcomes/results").glob("*.json")):
        record = json.loads(path.read_text())
        reading = record["packet"][2:].rsplit("-", 1)[0]
        for item in record["result"]["records"]:
            results[f"{reading}:{item['id']}"] = item
    summary = {}
    for name, reading in traces.items():
        recs, links = reading["records"], reading["links"]
        pauses = {p["pause"]: p for p in reading["pauses"]}
        rows = []
        for key, meta in index.items():
            if meta["reading"] != name:
                continue
            verdict = results[key]
            rid = meta["id"]
            later = [l for l in links if l["to"] == rid and l["from"] in recs and recs[l["from"]]["pause"] > meta["pause"]]
            marks = sorted({l["type"] for l in later if l["type"] in ("validates", "invalidates", "contradicts")})
            named_later = sorted({recs[k]["pause"] for k, r in recs.items() if r.get("pause", 0) > meta["pause"]
                                  and rid in (r.get("text") or "")} | {recs[l["from"]]["pause"] for l in later})
            thought_named = sorted({recs[k]["pause"] for k, r in recs.items() if r["layer"] == "thought"
                                    and r["pause"] > meta["pause"] and rid in (r.get("text") or "")} |
                                   {recs[l["from"]]["pause"] for l in later if recs[l["from"]]["layer"] == "thought"})
            where = locate(verdict.get("outcome_quote") or "", texts[name], len(texts[name]))
            rows.append({"key": key, **verdict, "id": rid, "pause": meta["pause"], "made_at": meta["end"],
                         "outcome_at": where, "reach": (where - meta["end"]) if where is not None else None,
                         "self_marks": marks, "named_later_at_pauses": named_later, "thought_named_at": thought_named})
        genuine = [r for r in rows if r["forward"] and not r["already_in_text"]]
        settled = [r for r in genuine if r["outcome"] != "never settled"]
        reaches = [r["reach"] for r in settled if r["reach"] is not None and r["reach"] > 0]
        summary[name] = {
            "records": len(rows), "genuine": len(genuine), "already_in_text": sum(r["already_in_text"] for r in rows),
            "not_forward": sum(not r["forward"] for r in rows),
            "outcomes": {o: sum(r["outcome"] == o for r in genuine) for o in ("borne out", "partly", "not borne out", "never settled")},
            "settled": len(settled), "settled_marked": sum(bool(r["self_marks"]) for r in settled),
            "settled_named_later": sum(bool(r["named_later_at_pauses"]) for r in settled),
            "settled_in_a_thought": sum(bool(r["thought_named_at"]) for r in settled),
            "reach_located": len(reaches), "reach_median": statistics.median(reaches) if reaches else None,
            "reach_over_10pct": sum(x >= 0.10 for x in reaches), "rows": rows}
        s = summary[name]
        print(f"{name}: {s['records']} records, {s['genuine']} genuine ({s['not_forward']} not forward, {s['already_in_text']} already in text); "
              f"outcomes {s['outcomes']}; settled {s['settled']}: marked by the reading {s['settled_marked']}, named or linked later "
              f"{s['settled_named_later']}, in a later thought {s['settled_in_a_thought']}; outcome located for {s['reach_located']}, "
              f"median reach {s['reach_median']:.3f} of the story, {s['reach_over_10pct']} reach 10% or more")
    (HERE / "outcomes/summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
