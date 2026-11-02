"""Summarise the blind development pass (development/results) per reading.

    python3 dev_summary.py

Per reading: revisions by kind and whether new text prompted them; resolved expectations and whether the checker
found the claim right; new expectations and how the story settles them; refusals to project; and references back,
with the earlier moment located in the story by its anchor phrase, measured as a fraction of the story before the
reflection's own position. Rates are per reflection and per 1,000 words of reflection (Core removed). Writes
development/summary.json.
"""
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from build_development import stories, utf16

HERE = Path(__file__).resolve().parent
RUN = HERE.parent


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def locate(anchor, story):
    a = norm(anchor)
    if len(a) < 15:
        return None
    at = story.find(a)
    if at < 0:
        at = story.find(a[:30]) if len(a) >= 30 else -1
    return at / len(story) if at >= 0 else None


def main():
    traces = json.loads((HERE / "traces.json").read_text())
    index = json.loads((HERE / "development/index.json").read_text())
    wyllie, johnston = stories()
    base = json.loads((RUN / "baseline/january-baseline.json").read_text())["source_boundaries_utf16"]
    texts = {"january": norm(utf16(wyllie, base["story_first_sentence"], base["gutenberg_end_marker"])),
             "understanding-graph": norm(johnston), "meaning-model": norm(johnston)}
    summary = {}
    for name, reading in traces.items():
        flat = [(p, t) for p in reading["pauses"] for t in p["thoughts"]]
        words = sum(len(re.findall(r"\w+", reading["records"][t]["text"])) for _, t in flat)
        per = {}
        for item in index:
            path = HERE / "development/results" / f"{item['packet']}.json"
            if item["reading"] != name or not path.exists():
                continue
            result = json.loads(path.read_text())["result"]
            for r in result["reflections"]:
                if item["analyse"][0] <= r["number"] <= item["analyse"][1]:
                    per[r["number"]] = r
        missing = [n for n in range(1, len(flat) + 1) if n not in per]
        rev = Counter()
        prompted = 0
        thoughts_with_revision = 0
        resolved, resolved_right = Counter(), Counter()
        exp_out = Counter()
        refusals = 0
        thoughts_with_refusal = 0
        refs, works, located, reaches = 0, 0, 0, []
        far_working = set()
        for number, (pause, thought) in enumerate(flat, 1):
            r = per.get(number, {})
            kinds = [x.get("kind") for x in r.get("revisions", [])]
            rev.update(kinds)
            prompted += sum(1 for x in r.get("revisions", []) if x.get("kind") != "bookkeeping" and x.get("prompted_by"))
            if any(k in ("overturn", "qualify", "correct") for k in kinds):
                thoughts_with_revision += 1
            for x in r.get("resolved_expectations", []):
                resolved[x.get("claimed")] += 1
                resolved_right[x.get("right")] += 1
            for x in r.get("expectations", []):
                exp_out[x.get("outcome")] += 1
            refusals += len(r.get("refusals", []))
            thoughts_with_refusal += bool(r.get("refusals"))
            for x in r.get("back_references", []):
                refs += 1
                works += x.get("work") == "works"
                where = locate(x.get("anchor"), texts[name])
                if where is not None:
                    located += 1
                    reach = max(0.0, pause["end"] - where)
                    reaches.append(reach)
                    if reach >= 0.10 and x.get("work") == "works":
                        far_working.add(number)
        n = len(flat)
        summary[name] = {
            "reflections": n, "analysed": len(per), "missing": missing, "words": words,
            "revisions": dict(rev), "interpretive_revisions": sum(rev[k] for k in ("overturn", "qualify", "correct")),
            "interpretive_prompted_by_text": prompted, "reflections_with_interpretive_revision": thoughts_with_revision,
            "resolved_expectations": dict(resolved), "resolved_right": dict(resolved_right),
            "expectations": sum(exp_out.values()), "expectation_outcomes": dict(exp_out),
            "refusals": refusals, "reflections_with_refusal": thoughts_with_refusal,
            "back_references": refs, "working": works, "anchors_located": located,
            "reach_median": statistics.median(reaches) if reaches else None,
            "references_reaching_10pct": sum(x >= 0.10 for x in reaches),
            "reflections_with_working_reference_10pct_back": len(far_working),
            "per_1000_words": {"interpretive_revisions": 1000 * sum(rev[k] for k in ("overturn", "qualify", "correct")) / words,
                               "expectations": 1000 * sum(exp_out.values()) / words, "refusals": 1000 * refusals / words,
                               "back_references": 1000 * refs / words}}
        s = summary[name]
        print(f"\n{name}: {n} reflections ({s['analysed']} analysed{', missing ' + str(missing) if missing else ''}), {words} words")
        print(f"  revisions {s['revisions']}; interpretive {s['interpretive_revisions']} ({s['interpretive_prompted_by_text']} prompted by new text), "
              f"in {thoughts_with_revision} reflections")
        print(f"  resolved expectations {s['resolved_expectations']}, right {s['resolved_right']}")
        print(f"  new expectations {s['expectations']}: {s['expectation_outcomes']}")
        print(f"  refusals {refusals} in {thoughts_with_refusal} reflections")
        print(f"  back references {refs} ({works} working), anchors located {located}, median reach {s['reach_median']}, "
              f"{s['references_reaching_10pct']} reach 10%+; reflections with a working reference 10%+ back: {len(far_working)}")
        print(f"  per 1,000 words: " + ", ".join(f"{k} {v:.1f}" for k, v in s["per_1000_words"].items()))
    (HERE / "development/summary.json").write_text(json.dumps(summary, indent=1) + "\n")


if __name__ == "__main__":
    main()
