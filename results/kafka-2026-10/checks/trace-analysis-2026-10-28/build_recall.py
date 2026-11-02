"""Build the checker-recall packets: copies of 30 checked packets, each with one planted error.

    python3 build_recall.py

recall/selection.json names ten thought packets per reading (seed 1028), alternating a planted claim from text not yet
read with a planted misreading of text already read. recall/plants.json holds the planted sentences, written by hand
against the text each packet gives. Each sentence is inserted after the first paragraph of the reflection (the prose
translation is left as it was), and the copy gets a new random id. recall/index.json maps the ids back. The original
packets and results are not touched.
"""
import json
import re
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent / "recall"


def main():
    selection = json.loads((HERE / "selection.json").read_text())
    plants = json.loads((HERE / "plants.json").read_text())
    out = HERE / "packets"
    out.mkdir(exist_ok=True)
    index = {}
    for item in selection:
        text = (HERE.parent / item["path"]).read_text()
        match = re.search(r"<<<REFLECTION\n(.*?)\nREFLECTION>>>", text, re.S)
        body = match.group(1)
        first, _, rest = body.partition("\n\n")
        planted = f"{first} {plants[item['packet']]}" + (f"\n\n{rest}" if rest else "")
        new = text[:match.start(1)] + planted + text[match.end(1):]
        blind = "R-" + secrets.token_hex(3)
        new = re.sub(r"^# Reflection \S+", f"# Reflection {blind}", new, count=1, flags=re.M)
        assert plants[item["packet"]] in new and new.count("<<<REFLECTION") == 1
        (out / f"{blind}.md").write_text(new)
        index[blind] = {**item, "plant": plants[item["packet"]]}
    (HERE / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    print(len(index), "packets")


if __name__ == "__main__":
    main()
