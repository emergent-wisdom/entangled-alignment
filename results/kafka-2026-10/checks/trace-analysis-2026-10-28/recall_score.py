"""Score the checker-recall run: did the checker report each planted sentence?

    python3 recall_score.py

A plant counts as caught when a reported misreading quotes at least six consecutive words of it. Also compares the
rest of each rerun's findings with the original run on the same packet (test-retest). Writes recall/score.json.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent


def words(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def overlaps(quote, plant, n=6):
    q, p = " ".join(words(quote)), words(plant)
    return any(" ".join(p[i:i + n]) in q for i in range(len(p) - n + 1))


def original(item):
    if item["reading"] == "meaning-model":
        path = RUN / "meaning-model-check/results" / f"{item['packet']}.json"
    else:
        path = RUN / "faithfulness-check/results" / f"{item['packet']}.json"
    return json.loads(path.read_text())["result"]["misreadings"]


def main():
    index = json.loads((HERE / "recall/index.json").read_text())
    rows = []
    for blind, item in index.items():
        found = json.loads((HERE / "recall/results" / f"{blind}.json").read_text())["result"]["misreadings"]
        hits = [m for m in found if overlaps(m.get("quote", ""), item["plant"])]
        others = [m for m in found if m not in hits]
        before = original(item)
        repeated = sum(any(overlaps(o.get("quote", ""), b.get("quote", ""), 5) or overlaps(b.get("quote", ""), o.get("quote", ""), 5)
                           for o in others) for b in before)
        rows.append({"blind": blind, "reading": item["reading"], "packet": item["packet"], "type": item["type"],
                     "plant": item["plant"], "caught": bool(hits), "as": [(m.get("kind"), m.get("severity")) for m in hits],
                     "other_findings": len(others), "original_findings": len(before), "original_found_again": repeated})
    out = {}
    for key in ("read-ahead", "misreading"):
        sel = [r for r in rows if r["type"] == key]
        out[key] = {"caught": sum(r["caught"] for r in sel), "of": len(sel)}
    for reading in ("january", "understanding-graph", "meaning-model"):
        sel = [r for r in rows if r["reading"] == reading]
        if not sel:
            continue
        out[reading] = {"caught": sum(r["caught"] for r in sel), "of": len(sel),
                        "original_findings": sum(r["original_findings"] for r in sel),
                        "original_found_again": sum(r["original_found_again"] for r in sel),
                        "other_findings": sum(r["other_findings"] for r in sel)}
    (HERE / "recall/score.json").write_text(json.dumps({"summary": out, "rows": rows}, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1))
    for r in rows:
        if not r["caught"]:
            print("MISSED", r["reading"], r["packet"], r["type"], r["plant"])


if __name__ == "__main__":
    main()
