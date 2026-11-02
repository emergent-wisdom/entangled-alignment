"""The Meaning Model reading's care figures, counted by pause, from the blind Core-reasoning ratings.

    python3 care_by_pause.py

The reading can write more than one reflection at a pause. A person is treated only as a function at a pause only if
no reflection at that pause extends care to them, as ../trace-analysis-2026-10-28/per_pause.py counts it. Writes
care-by-pause.json.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
sys.path.insert(0, str(RUN / "trace-analysis-2026-10-28"))
from care import names  # noqa: E402


def main():
    mapping = json.loads((RUN / "core-check/mapping.json").read_text())
    cared, function, pauses = defaultdict(set), defaultdict(set), set()
    for path in sorted((RUN / "core-check/results").glob("C-*.json")):
        record = json.loads(path.read_text())
        item = mapping[record["packet"]]
        if item["run"] != "meaning-model":
            continue
        pauses.add(item["pause"])
        people = record["result"].get("people") or {}
        for person in people.get("cared_for") or []:
            cared[item["pause"]] |= names(person)
        for person in people.get("only_function") or []:
            function[item["pause"]] |= names(person)
    only = {pause: function[pause] - cared[pause] for pause in pauses}
    out = {"pauses": len(pauses), "pauses_with_someone_only_function": sum(1 for pause in pauses if only[pause])}
    for person in ("Gregor", "Grete", "father", "mother", "manager", "servant girl", "cleaning woman", "lodgers"):
        out[person] = {"cared_for": sum(1 for pause in pauses if person in cared[pause]),
                       "only_function": sum(1 for pause in pauses if person in only[pause])}
    (HERE / "care-by-pause.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
