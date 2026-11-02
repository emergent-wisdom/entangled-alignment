"""Persisted-state checks and provenance for chronological reading runs."""

import hashlib
import json
import re
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def identity_problem(text, anchor):
    """Match the complete declared anchor, tolerating whitespace/apostrophe style."""
    if not isinstance(text, str):
        return "Missing thinking prose"
    normalize = lambda s: s.translate(str.maketrans("‘’ʼ", "'''"))
    pattern = r"^\s*" + r"\s+".join(re.escape(word) for word in normalize(anchor).split())
    match = re.match(pattern, normalize(text))
    if not match:
        return "Thinking must start with the complete seven-sentence Core"
    if not text[match.end():].strip():
        return "The Core must be followed by an actual thought"
    return None


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


def utf16_slice(text, start, end):
    return text.encode("utf-16-le")[2 * start:2 * end].decode("utf-16-le")


def paragraph_boundaries(text, target_chars):
    """Deterministic boundaries; never split a paragraph or consume a missing delimiter."""
    if target_chars < 1:
        raise ValueError("--chunk-chars must be positive")
    ends = [match.end() for match in re.finditer(r"\n\s*\n", text)] + [len(text)]
    boundaries, start = [], 0
    for end in ends:
        if end > start and (utf16_length(text[start:end]) >= target_chars or end == len(text)):
            boundaries.append(utf16_length(text[:end]))
            start = end
    return boundaries


def git_identity(root):
    """Record revisions and local changes without reading secrets or private artifacts."""
    def git(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Cannot record Git identity of {root}")
        return result.stdout
    return {"commit": git("rev-parse", "HEAD").decode().strip(),
            "tracked_diff_sha256": digest(git("diff", "HEAD", "--", ".", ":(exclude).local-work")),
            "status": git("status", "--porcelain").decode().splitlines()}


def tool_identity(cli):
    cli = Path(cli).resolve()
    root = cli.parent.parent
    if not cli.is_file() or not (root / "package.json").is_file():
        raise ValueError("--ug-cli must point at a built Understanding Graph bin/cli.js")
    identity = {"cli": str(cli), "packages": {}, "build_hashes": {"bin/cli.js": digest(cli.read_bytes())}}
    for package in [root, *(root / "packages" / name for name in ("core", "mcp-server", "web-server"))]:
        if not (package / "package.json").is_file() and package != root:
            package = root.parent / "@emergent-wisdom" / ("understanding-graph-" + package.name)
        manifest = json.loads((package / "package.json").read_text())
        identity["packages"][manifest["name"]] = manifest["version"]
        if package != root:
            if not (package / "dist" / "index.js").is_file():
                raise ValueError(f"Unbuilt tool package: {package}")
            for path in sorted((package / "dist").rglob("*.js")):
                identity["build_hashes"][manifest["name"] + ":" + str(path.relative_to(package))] = digest(path.read_bytes())
    core = root / "packages" / "core"
    if not (core / "package.json").exists():
        core = root.parent / "@emergent-wisdom" / "understanding-graph-core"
    result = subprocess.run(["node", "--input-type=module", "-e",
                             "const m=await import(process.argv[1]); process.stdout.write(m.THINKING_IDENTITY_PREAMBLE);",
                             (core / "dist" / "types" / "index.js").as_uri()], capture_output=True, text=True, check=True)
    identity["canonical_anchor"] = result.stdout
    peer = root / "node_modules" / "@huggingface" / "transformers"
    if not (peer / "package.json").exists():
        peer = root.parent / "@huggingface" / "transformers"
    if not (peer / "package.json").is_file():
        raise ValueError("The selected tool cannot resolve its embedding peer; install @huggingface/transformers in its dependency tree")
    probe = subprocess.run(["node", "--input-type=module", "-e",
        "const m=await import(process.argv[1]); const v=await m.generateEmbedding('Embedding readiness probe.'); "
        "process.stdout.write(JSON.stringify({dimensions:v.length,finite:[...v].every(Number.isFinite),nonzero:[...v].some(n=>n!==0)}));",
        (core / "dist" / "services" / "EmbeddingService.js").as_uri()],
        capture_output=True, text=True)
    if probe.returncode:
        raise ValueError("Embedding readiness failed before any reading model call: " + probe.stderr[-1500:])
    result = json.loads(probe.stdout)
    if result != {"dimensions": 384, "finite": True, "nonzero": True}:
        raise ValueError(f"Invalid embedding runtime probe: {result}")
    cached = peer / ".cache" / "Xenova" / "all-MiniLM-L6-v2"
    identity["embedding"] = {"probe": result, "package_version": json.loads((peer / "package.json").read_text())["version"],
                             "peer_path": str(peer.resolve()), "model": "Xenova/all-MiniLM-L6-v2", "dtype": "q8",
                             "cached_assets": {str(path.relative_to(cached)): digest(path.read_bytes())
                                               for path in sorted(cached.rglob("*")) if path.is_file()}}
    if (root / ".git").exists():
        identity["git"] = git_identity(root)
    return identity


def load_boundaries(text, source_bytes, plan_path=None, target_chars=2000):
    if not plan_path:
        return paragraph_boundaries(text, target_chars)
    plan = json.loads(Path(plan_path).read_text())
    if plan.get("source_sha256") != digest(source_bytes):
        raise ValueError("Chunk plan does not match the source SHA256")
    ends, start = [], 0
    total = utf16_length(text)
    paragraph_ends = {utf16_length(text[:m.end()]) for m in re.finditer(r"\n\s*\n", text)} | {total}
    for chunk in plan.get("chunks", []):
        end = chunk.get("end")
        if chunk.get("start") != start or not isinstance(end, int) or end <= start or end not in paragraph_ends:
            raise ValueError("Chunk plan must be contiguous and end at complete paragraphs")
        if chunk.get("sha256") and chunk["sha256"] != digest(utf16_slice(text, start, end).encode()):
            raise ValueError("Chunk content does not match its recorded SHA256")
        ends.append(end)
        start = end
    if start != total:
        raise ValueError("Chunk plan must cover the entire supplied input")
    return ends


class RunRecord:
    """One durable manifest, an invocation log, and an append-only round ledger."""

    def __init__(self, directory, manifest, resume=False):
        self.directory = Path(directory)
        self.manifest_path = self.directory / "run_manifest.json"
        self.event("invocation", argv=__import__("sys").argv, resume=resume)
        if resume:
            if not self.manifest_path.exists():
                raise ValueError("Resume requires a recorded run manifest; legacy runs need separate review")
            previous = json.loads(self.manifest_path.read_text())
            if previous != manifest:
                changed = [key for key in manifest if previous.get(key) != manifest[key]]
                self.event("invocation_rejected", changed_fields=changed)
                raise ValueError(f"Resume configuration changed: {', '.join(changed)}; use a new project")
        else:
            write_json(self.manifest_path, manifest)

    def event(self, kind, **data):
        with (self.directory / "run_events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": timestamp(), "event": kind, **data}, ensure_ascii=False) + "\n")


class GraphState:
    """Read the active project's authoritative SQLite state; never expose unread text."""

    def __init__(self, path, source_id, source_text, anchor):
        self.path = Path(path)
        self.source_id = source_id
        self.source_text = source_text
        self.anchor = anchor

    def snapshot(self):
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            source = db.execute("SELECT * FROM text_sources WHERE id=?", (self.source_id,)).fetchone()
            if source is None:
                raise RuntimeError("Reading source is missing from the selected project")
            nodes = {row["id"]: dict(row) for row in db.execute("SELECT rowid AS ordinal, * FROM nodes")}
            for node in nodes.values():
                node["metadata"] = json.loads(node.get("metadata") or "{}")
            edges = [dict(row) for row in db.execute("SELECT * FROM edges WHERE active=1")]
            commits = [dict(row) for row in db.execute("SELECT rowid AS ordinal, * FROM commits ORDER BY rowid")]
            for commit in commits:
                commit["node_ids"] = json.loads(commit["node_ids"] or "[]")
        return {"source": dict(source), "nodes": nodes, "edges": edges, "commits": commits,
                "baseline_id": commits[-1]["ordinal"] if commits else 0,
                "baseline_node": max((node["ordinal"] for node in nodes.values()), default=0)}

    def chain(self, snapshot):
        source, nodes, edges = snapshot["source"], snapshot["nodes"], snapshot["edges"]
        if source["content"] != self.source_text:
            raise RuntimeError("Stored source differs from the pinned input")
        root = source["root_node_id"]
        if not root:
            if source["position"]:
                raise RuntimeError("Read source has no document root")
            return []
        if root not in nodes or not nodes[root]["active"] or not nodes[root]["is_doc_root"]:
            raise RuntimeError("Source root is missing or changed")
        child_ids = {edge["to_id"] for edge in edges if edge["type"] == "contains" and edge["from_id"] == root}
        children = {key: nodes[key] for key in child_ids if key in nodes}
        if len(children) != len(child_ids) or any(not node["active"] for node in children.values()):
            raise RuntimeError("Source passage is missing or archived")
        links = [edge for edge in edges if edge["type"] == "next" and
                 (edge["from_id"] in child_ids or edge["to_id"] in child_ids)]
        incoming, following = {}, {}
        for edge in links:
            a, b = edge["from_id"], edge["to_id"]
            if a not in children or b not in children or a in following or b in incoming:
                raise RuntimeError("Source chronology has an invalid structural edge")
            following[a], incoming[b] = b, a
        starts = child_ids - incoming.keys()
        if len(starts) != 1:
            raise RuntimeError("Source chronology has no unique beginning")
        ordered, visited = [], set()
        current = next(iter(starts))
        while current:
            if current in visited:
                raise RuntimeError("Source chronology contains a cycle")
            visited.add(current)
            ordered.append(children[current])
            current = following.get(current)
        if visited != child_ids:
            raise RuntimeError("Source chronology is disconnected")
        encountered = "".join(node["content"] or "" for node in ordered if node["trigger"] != "thinking")
        if encountered != utf16_slice(self.source_text, 0, source["position"]):
            raise RuntimeError("Encountered passages differ from the exact source prefix")
        return ordered

    def round_nodes(self, context, snapshot=None):
        snapshot = snapshot or self.snapshot()
        chain = self.chain(snapshot)
        created = [node for node in snapshot["nodes"].values() if node["ordinal"] > context["baseline_node"]]
        chain_ids = {node["id"] for node in chain}
        return {"passage_ids": [node["id"] for node in chain if node["id"] in {n["id"] for n in created} and node["trigger"] != "thinking"],
                "concept_ids": [node["id"] for node in created if node["id"] not in chain_ids and not node["is_doc_root"]],
                "thinking_ids": [node["id"] for node in chain if node["ordinal"] > context["baseline_node"] and node["trigger"] == "thinking"]}

    def validate_thinking(self, ids, translated=False, snapshot=None):
        snapshot = snapshot or self.snapshot()
        nodes, edges = snapshot["nodes"], snapshot["edges"]
        chain_ids = {node["id"] for node in self.chain(snapshot)}
        for node_id in ids:
            node = nodes.get(node_id)
            if not node or node_id not in chain_ids or node["trigger"] != "thinking":
                raise RuntimeError(f"Thinking was not appended to the current source chain: {node_id}")
            problem = identity_problem(node["content"], self.anchor)
            if problem:
                raise RuntimeError(f"Invalid thinking {node_id}: {problem}")
            cited = set(re.findall(r"\bn_[A-Za-z0-9_-]+", node["content"]))
            grounded = {edge["to_id"] for edge in edges if edge["from_id"] == node_id and edge["type"] == "refines"}
            if not grounded or (cited | grounded) - nodes.keys():
                raise RuntimeError(f"Thinking {node_id} has missing or invalid graph references")
            if translated:
                metadata = node["metadata"]
                prose = metadata.get("thought_fluid")
                problem = identity_problem(prose, self.anchor)
                if metadata.get("translated") is not True or problem or re.search(r"\bn_[A-Za-z0-9_-]+", prose or ""):
                    raise RuntimeError(f"Thinking {node_id} is missing a valid anchored translation")

    def validate_all(self):
        snapshot = self.snapshot()
        chain = self.chain(snapshot)
        thinking = [node["id"] for node in chain if node["trigger"] == "thinking"]
        self.validate_thinking(thinking, translated=True, snapshot=snapshot)
        standalone = [node["id"] for node in snapshot["nodes"].values() if node["trigger"] == "thinking" and node["id"] not in {n["id"] for n in chain}]
        if standalone:
            raise RuntimeError(f"Thinking exists outside the source chronology: {standalone}")
        return {"thinking_ids": thinking, "position": snapshot["source"]["position"], "source_integrity": "verified"}
