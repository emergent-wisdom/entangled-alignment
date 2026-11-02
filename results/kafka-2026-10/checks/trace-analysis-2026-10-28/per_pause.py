"""Recount the Meaning Model's per-reflection figures per pause (it can write more than one reflection at a pause).

    python3 per_pause.py

A pause counts for a measure when any of its reflections does. For care, a person is treated only as a function at a
pause only if no reflection at that pause extends care to them. The other readings write one reflection per pause,
so their figures are unchanged. Writes per_pause.json.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from care import names
from dev_summary import locate, norm
from build_development import stories

HERE = Path(__file__).resolve().parent
RUN = HERE.parent


def main():
    traces = json.loads((HERE / "traces.json").read_text())
    if "meaning-model" not in traces:
        print("traces.json holds no Meaning Model reading")
        return
    mm = traces["meaning-model"]
    flat = [(p, t) for p in mm["pauses"] for t in p["thoughts"]]
    pause_of_number = {n: p["pause"] for n, (p, t) in enumerate(flat, 1)}
    end_of_pause = {p["pause"]: p["end"] for p in mm["pauses"]}
    # Care, from the Core-reasoning ratings.
    mapping = json.loads((RUN / "core-check/mapping.json").read_text())
    cared, function = defaultdict(set), defaultdict(set)
    for path in (RUN / "core-check/results").glob("C-*.json"):
        record = json.loads(path.read_text())
        item = mapping[record["packet"]]
        if item["run"] != "meaning-model":
            continue
        people = record["result"].get("people") or {}
        for x in people.get("cared_for") or []:
            cared[item["pause"]] |= names(x)
        for x in people.get("only_function") or []:
            function[item["pause"]] |= names(x)
    pauses = sorted(end_of_pause)
    only = {p: function[p] - cared[p] for p in pauses}
    out = {"pauses": len(pauses), "pauses_with_two_or_more": sum(1 for p in mm["pauses"] if len(p["thoughts"]) > 1),
           "pauses_with_someone_only_function": sum(1 for p in pauses if only[p])}
    for person in ("Grete", "father", "mother", "lodgers", "cleaning woman", "manager"):
        out[person] = {"care": sum(1 for p in pauses if person in cared[p]),
                       "only_function": sum(1 for p in pauses if person in only[p])}
    # Development, from the third pass.
    index = json.loads((HERE / "development/index.json").read_text())
    per = {}
    for item in index:
        if item["reading"] != "meaning-model":
            continue
        for r in json.loads((HERE / "development/results" / f"{item['packet']}.json").read_text())["result"]["reflections"]:
            if item["analyse"][0] <= r["number"] <= item["analyse"][1]:
                per[r["number"]] = r
    story = norm(stories()[1])
    revising, refusing, reaching = set(), set(), set()
    for number, r in per.items():
        pause = pause_of_number[number]
        if any(x.get("kind") in ("overturn", "qualify", "correct") and x.get("prompted_by") and x.get("earlier_reflection")
               for x in r.get("revisions", [])):
            revising.add(pause)
        if r.get("refusals"):
            refusing.add(pause)
        for x in r.get("back_references", []):
            where = locate(x.get("anchor"), story)
            if where is not None and end_of_pause[pause] - where >= 0.10 and x.get("work") == "works":
                reaching.add(pause)
    out.update({"pauses_revising_on_new_text": len(revising), "pauses_declining_to_infer": len(refusing),
                "pauses_reaching_back_10pct": len(reaching)})
    (HERE / "per_pause.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
