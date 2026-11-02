"""Unblind the faithfulness results and sum them per run.

    python3 aggregate.py

Writes summary.json and findings.md (every reported misreading, by run and thought, with its quotes).
Verification marks, when present in verification.json ({blind: {index: "confirmed"|"rejected"|"partly"}}),
are applied and counted separately.
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
mapping = json.loads((HERE / "mapping.json").read_text())
verdicts = json.loads((HERE / "verification.json").read_text()) if (HERE / "verification.json").exists() else {}


def words(blind):
    text = (HERE / "packets" / f"{blind}.md").read_text()
    raw = text.split("<<<REFLECTION\n", 1)[1].split("\nREFLECTION>>>", 1)[0]
    fluid = text.split("<<<TRANSLATION\n", 1)[1].split("\nTRANSLATION>>>", 1)[0]
    return len(raw.split()), len(fluid.split())


summary, lines = {}, ["# Reported misreadings, unblinded\n"]
for run in ("january", "several"):
    blinds = sorted((b for b, m in mapping.items() if m["run"] == run), key=lambda b: mapping[b]["thought"])
    missing = [b for b in blinds if not (HERE / "results" / f"{b}.json").exists()]
    severity, kinds, confirmed = collections.Counter(), collections.Counter(), collections.Counter()
    statements = raw_words = fluid_words = flagged = 0
    lines.append(f"\n## {run} ({len(blinds)} thoughts)\n")
    for blind in blinds:
        path = HERE / "results" / f"{blind}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text())["result"]
        r, f = words(blind)
        raw_words += r; fluid_words += f
        statements += int(result.get("factual_statements_checked") or 0)
        found = result["misreadings"]
        flagged += bool(found)
        for index, item in enumerate(found):
            verdict = verdicts.get(blind, {}).get(str(index))
            severity[item.get("severity")] += 1
            kinds[item.get("kind")] += 1
            if verdict:
                confirmed[(verdict, item.get("severity"))] += 1
            lines.append(f"- **Thought {mapping[blind]['thought']}** ({blind}, #{index}) [{item.get('severity')}, {item.get('kind')}, "
                         f"{item.get('version')}]{' — ' + verdict.upper() if verdict else ''}\n"
                         f"  - Reflection: \"{item.get('quote')}\"\n  - Text: \"{item.get('evidence')}\"\n"
                         f"  - {item.get('explanation')}\n")
    total = sum(severity.values())
    summary[run] = {"thoughts": len(blinds), "checked": len(blinds) - len(missing), "missing": missing,
                    "thoughts_with_any_misreading": flagged, "misreadings": total,
                    "by_severity": dict(severity), "by_kind": dict(kinds),
                    "misreadings_per_thought": round(total / max(1, len(blinds) - len(missing)), 2),
                    "statements_checked": statements,
                    "misreadings_per_100_statements": round(100 * total / statements, 1) if statements else None,
                    "reflection_words": raw_words, "translation_words": fluid_words,
                    "misreadings_per_1000_reflection_words": round(1000 * total / raw_words, 2) if raw_words else None,
                    "verification": {f"{v}/{s}": n for (v, s), n in sorted(confirmed.items())}}
(HERE / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
(HERE / "findings.md").write_text("\n".join(lines) + "\n")
print(json.dumps(summary, indent=1))
