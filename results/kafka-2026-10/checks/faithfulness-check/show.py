import json, re, sys
from pathlib import Path
mapping = json.load(open("mapping.json"))
run, severities = sys.argv[1], set(sys.argv[2].split(","))
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0; count = int(sys.argv[4]) if len(sys.argv) > 4 else 999
def norm(s): return re.sub(r"\s+", " ", s or "")
def ctx(text, ev, claim):
    t = norm(text)
    for piece in [p.strip(' "“”') for p in re.split(r"\.\.\.|…|\";|\" ;", ev or "") if len(p.strip()) > 12]:
        i = t.find(norm(piece)[:60])
        if i >= 0: return t[max(0, i - 220): i + len(piece) + 220]
    rare = sorted(set(re.findall(r"[A-Za-z]{6,}", (ev or "") + " " + (claim or ""))), key=lambda w: t.count(w) or 9999)
    for w in rare:
        i = t.find(w)
        if i >= 0: return "(anchor " + w + ") " + t[max(0, i - 250): i + 300]
    return "(no anchor)"
items = []
for blind, m in sorted(mapping.items(), key=lambda x: x[1]["thought"]):
    if m["run"] != run: continue
    pk = Path("packets", f"{blind}.md").read_text()
    text = pk.split("<<<TEXT\n", 1)[1].split("\nTEXT>>>", 1)[0]
    for i, it in enumerate(json.load(open(f"results/{blind}.json"))["result"]["misreadings"]):
        if it["severity"] in severities: items.append((m["thought"], blind, i, it, text))
for th, blind, i, it, text in items[start:start + count]:
    print(f"### {run} thought {th} {blind}#{i} [{it['severity']}/{it['kind']}/{it['version']}]")
    print("  CLAIM:", it["quote"]); print("  EVIDENCE:", it["evidence"][:400]); print("  WHY:", it["explanation"])
    print("  CONTEXT:", ctx(text, it["evidence"], it["quote"])[:700])
print(f"[{len(items)} items in total]")
