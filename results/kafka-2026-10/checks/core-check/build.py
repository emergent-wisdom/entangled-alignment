"""Build Core-reasoning packets from the accuracy-check packets: the passage just read and the reflection (Core removed).

    python3 build.py

Sources: ../faithfulness-check/packets (January and the Understanding Graph several-nodes reading, mapped in its
mapping.json) and ../meaning-model-check/packets/T-*.md (the Meaning Model reading). Each packet gets a random id; the
mapping is written to mapping.json. Re-running adds only reflections not yet packed.
"""
import json
import re
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
PACKETS = HERE / "packets"


def blocks(text):
    return {name: body for name, body in re.findall(r"<<<([A-Z]+)\n(.*?)\n\1>>>", text, re.S)}


def main():
    PACKETS.mkdir(exist_ok=True)
    mapping_path = HERE / "mapping.json"
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    packed = {(item["run"], item["source_packet"]) for item in mapping.values()}
    sources = []
    earlier = json.loads((RUN / "faithfulness-check" / "mapping.json").read_text())
    for packet, item in earlier.items():
        sources.append((item["run"], packet, RUN / "faithfulness-check" / "packets" / f"{packet}.md", item))
    for path in sorted((RUN / "meaning-model-check" / "packets").glob("T-*.md")):
        pause, number = path.stem.split("-")[1:]
        sources.append(("meaning-model", path.stem, path, {"pause": int(pause), "thought_in_pause": int(number)}))
    added = 0
    for run, packet, path, item in sources:
        if (run, packet) in packed:
            continue
        found = blocks(path.read_text())
        text = "\n\n".join(["# One reflection", "## The passage the reader had just read",
                            f"<<<PASSAGE\n{found['PASSAGE']}\nPASSAGE>>>",
                            "## The reflection (the Core recital removed)", f"<<<REFLECTION\n{found['REFLECTION']}\nREFLECTION>>>"])
        key = "C-" + secrets.token_hex(3)
        while key in mapping:
            key = "C-" + secrets.token_hex(3)
        (PACKETS / f"{key}.md").write_text(text + "\n")
        mapping[key] = {"run": run, "source_packet": packet, **{k: v for k, v in item.items() if k != "run"}}
        added += 1
    mapping_path.write_text(json.dumps(mapping, indent=1) + "\n")
    counts = {}
    for item in mapping.values():
        counts[item["run"]] = counts.get(item["run"], 0) + 1
    print(json.dumps({"added": added, "by_run": counts}))


if __name__ == "__main__":
    main()
