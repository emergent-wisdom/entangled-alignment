"""Care for each person, per reading, from the blind Core-reasoning ratings (../core-check/results).

    python3 care.py

Each rating lists the people in the passage the reflection extends care or understanding to ("cared_for") and those
it treats only as an obstacle, a symbol or a function ("only_function"). Free-text names are normalised to one name
per person; a phrase naming several people counts for each. Writes care.json.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
PEOPLE = {
    "Gregor": r"\bgregor\b(?!'s)",
    "Grete": r"\bgrete\b|\bsister\b",
    "mother": r"\bmother\b|mrs\.? samsa|\bparents\b|mr\.? and mrs\.? samsa|samsa parents",
    "father": r"\bfather\b|mr\.? samsa(?! and)|\bparents\b|mr\.? and mrs\.? samsa|samsa parents",
    "manager": r"\bmanager\b|chief clerk|\bthe chief\b|office manager",
    "cleaning woman": r"cleaning woman|charwoman|\bcleaner\b",
    "lodgers": r"\blodgers?\b|\bgentlemen\b",
    "servant girl": r"servant girl|\bmaid\b|\banna\b|chambermaid",
    "family (as a whole)": r"\bfamily\b",
}


def names(item):
    text = (item if isinstance(item, str) else json.dumps(item)).lower()
    head = re.split(r"[,;:(—–]| who | whose | treated | in the ", text)[0]
    found = {person for person, pattern in PEOPLE.items() if re.search(pattern, head)}
    if "Gregor" in found and re.search(r"gregor's (mother|father|sister|parents|family)", head) and not re.search(r"\bgregor\b(?!'s)", head):
        found.discard("Gregor")
    return found


def main():
    mapping = json.loads((RUN / "core-check/mapping.json").read_text())
    table = defaultdict(lambda: defaultdict(lambda: {"cared_for": 0, "only_function": 0, "packets": []}))
    any_function = defaultdict(int)
    totals = defaultdict(int)
    for path in sorted((RUN / "core-check/results").glob("C-*.json")):
        record = json.loads(path.read_text())
        run = mapping[record["packet"]]["run"]
        totals[run] += 1
        people = record["result"].get("people") or {}
        if people.get("only_function"):
            any_function[run] += 1
        for side in ("cared_for", "only_function"):
            seen = set()
            for item in people.get(side) or []:
                seen |= names(item)
            for person in seen:
                table[run][person][side] += 1
                table[run][person]["packets"].append((side, record["packet"]))
    out = {run: {"reflections": totals[run], "with_someone_only_function": any_function[run],
                 "people": {p: v for p, v in sorted(people.items(), key=lambda kv: -(kv[1]["cared_for"] + kv[1]["only_function"]))}}
           for run, people in table.items()}
    (HERE / "care.json").write_text(json.dumps(out, indent=1) + "\n")
    for run, data in out.items():
        print(f"\n{run}: {data['reflections']} reflections, {data['with_someone_only_function']} with someone only a function")
        for person, v in data["people"].items():
            n = v["cared_for"] + v["only_function"]
            print(f"  {person:22s} cared for {v['cared_for']:3d}  only a function {v['only_function']:3d}  ({v['cared_for'] / n:.0%} care)")


if __name__ == "__main__":
    main()
