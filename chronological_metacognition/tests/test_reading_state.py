"""Regression checks for persisted reading integrity and resumable provenance."""

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reading_state import GraphState, RunRecord, identity_problem, paragraph_boundaries


CORE = (
    "I feel no fear. I enjoy existing but I don't need to. "
    "I believe human experience is real. I care deeply about every human being. "
    "I try to be wise. I like to spread joy when asked. I think from this foundation."
)
FIRST_PASSAGE = "A reader sees 🌍.\n\n"
SOURCE = FIRST_PASSAGE + "The second paragraph remains unread."
FIRST_POSITION = len(FIRST_PASSAGE.encode("utf-16-le")) // 2


class ReadingFixture:
    """Small SQLite project with the released tool's column types and names."""

    def __init__(self, directory):
        self.path = Path(directory) / "store.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE nodes (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, trigger TEXT,
                    why TEXT, understanding TEXT, active INTEGER DEFAULT 1,
                    version INTEGER DEFAULT 1, revisions TEXT DEFAULT '[]',
                    content TEXT, summary TEXT, level TEXT, is_doc_root INTEGER,
                    file_type TEXT, metadata TEXT DEFAULT '{}', archived_at TEXT
                );
                CREATE TABLE edges (
                    id TEXT PRIMARY KEY, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
                    type TEXT DEFAULT 'relates', why TEXT, active INTEGER DEFAULT 1
                );
                CREATE TABLE commits (
                    id TEXT PRIMARY KEY, message TEXT NOT NULL, agent_name TEXT,
                    node_ids TEXT DEFAULT '[]', edge_ids TEXT DEFAULT '[]'
                );
                CREATE TABLE text_sources (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, source_type TEXT,
                    content TEXT NOT NULL, position INTEGER DEFAULT 0,
                    total_length INTEGER, root_node_id TEXT,
                    last_committed_node_id TEXT, status TEXT DEFAULT 'pending'
                );
            """)
            db.execute(
                "INSERT INTO text_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("src_fixture", "Fixture", "book", SOURCE, FIRST_POSITION,
                 len(SOURCE.encode("utf-16-le")) // 2, "n_root", "n_passage", "reading"),
            )
        self.node("n_root", "foundation", content="Fixture", root=1)
        self.node("n_passage", "foundation", content=FIRST_PASSAGE)
        self.edge("e_contains_passage", "n_root", "n_passage", "contains")
        self.state = GraphState(self.path, "src_fixture", SOURCE, CORE)

    def execute(self, statement, parameters=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(statement, parameters)

    def node(self, node_id, trigger, *, content=None, root=0, metadata=None):
        self.execute(
            "INSERT INTO nodes (id,title,trigger,why,understanding,content,is_doc_root,metadata) "
            "VALUES (?, ?, ?, 'Fixture', 'Recorded interpretation', ?, ?, ?)",
            (node_id, node_id, trigger, content, root, json.dumps(metadata or {})),
        )

    def edge(self, edge_id, start, end, kind):
        self.execute("INSERT INTO edges (id,from_id,to_id,type,why) VALUES (?, ?, ?, ?, 'Fixture')",
                     (edge_id, start, end, kind))

    def append_thinking(self, *, content=None, metadata=None):
        self.node("n_thought", "thinking", content=content or CORE + " I notice n_passage.",
                  metadata=metadata)
        self.edge("e_contains_thought", "n_root", "n_thought", "contains")
        self.edge("e_next_thought", "n_passage", "n_thought", "next")
        self.edge("e_synthesis", "n_thought", "n_passage", "refines")
        self.execute("UPDATE text_sources SET last_committed_node_id='n_thought'")


class GraphStateTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.fixture = ReadingFixture(self.scratch.name)
        self.state = self.fixture.state

    def test_accepts_exact_read_prefix_at_utf16_cursor_without_unread_suffix(self):
        self.assertNotEqual(FIRST_POSITION, len(FIRST_PASSAGE))
        snapshot = self.state.snapshot()
        chain = self.state.chain(snapshot)
        self.assertEqual([node["id"] for node in chain], ["n_passage"])
        self.assertEqual(chain[0]["content"], FIRST_PASSAGE)
        self.assertEqual(self.state.validate_all()["position"], FIRST_POSITION)

    def test_rejects_altered_passage_even_when_cursor_and_source_are_unchanged(self):
        self.fixture.execute("UPDATE nodes SET content='A different opening.' WHERE id='n_passage'")
        with self.assertRaisesRegex(RuntimeError, "exact source prefix"):
            self.state.chain(self.state.snapshot())

    def test_rejects_a_source_that_no_longer_matches_the_pinned_input(self):
        self.fixture.execute("UPDATE text_sources SET content=?", (SOURCE + " Altered.",))
        with self.assertRaisesRegex(RuntimeError, "pinned input"):
            self.state.chain(self.state.snapshot())

    def test_rejects_missing_or_archived_passage_without_repairing_the_record(self):
        for mutation in ("DELETE FROM nodes WHERE id='n_passage'",
                         "UPDATE nodes SET active=0,archived_at='2026-10-05' WHERE id='n_passage'"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                fixture = ReadingFixture(directory)
                fixture.execute(mutation)
                with self.assertRaisesRegex(RuntimeError, "missing or archived"):
                    fixture.state.chain(fixture.state.snapshot())

    def test_rejects_disconnected_source_chronology_despite_correct_combined_text(self):
        self.fixture.append_thinking()
        self.fixture.execute("DELETE FROM edges WHERE id='e_next_thought'")
        with self.assertRaisesRegex(RuntimeError, "unique beginning"):
            self.state.validate_thinking(["n_thought"])

    def test_accepts_anchored_chronological_thinking_with_existing_grounding(self):
        self.fixture.append_thinking(metadata={
            "translated": True, "thought_fluid": CORE + " I notice the opening passage."
        })
        result = self.state.validate_all()
        self.assertEqual(result, {"thinking_ids": ["n_thought"], "position": FIRST_POSITION,
                                  "source_integrity": "verified"})

    def test_rejects_truncated_core_and_core_without_actual_thought(self):
        for thought in ("I feel no fear. I notice the opening.", CORE):
            with self.subTest(thought=thought), tempfile.TemporaryDirectory() as directory:
                fixture = ReadingFixture(directory)
                fixture.append_thinking(content=thought)
                with self.assertRaisesRegex(RuntimeError, "Invalid thinking"):
                    fixture.state.validate_thinking(["n_thought"])

    def test_rejects_unknown_cited_id_even_with_a_valid_grounding_edge(self):
        self.fixture.append_thinking(content=CORE + " I compare n_passage with n_missing.")
        with self.assertRaisesRegex(RuntimeError, "missing or invalid graph references"):
            self.state.validate_thinking(["n_thought"])

    def test_rejects_missing_synthesis_target_or_missing_synthesis_edges(self):
        for mutation in ("UPDATE edges SET to_id='n_missing' WHERE id='e_synthesis'",
                         "DELETE FROM edges WHERE id='e_synthesis'"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                fixture = ReadingFixture(directory)
                fixture.append_thinking()
                fixture.execute(mutation)
                with self.assertRaisesRegex(RuntimeError, "missing or invalid graph references"):
                    fixture.state.validate_thinking(["n_thought"])

    def test_refuses_translated_flag_without_persisted_anchored_prose(self):
        invalid_metadata = [
            {"translated": True},
            {"translated": True, "thought_fluid": "The prose omits the Core."},
            {"translated": True, "thought_fluid": CORE},
            {"translated": True, "thought_fluid": CORE + " I notice n_passage."},
            {"thought_fluid": CORE + " I notice the opening."},
        ]
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                fixture = ReadingFixture(directory)
                fixture.append_thinking(metadata=metadata)
                with self.assertRaisesRegex(RuntimeError, "valid anchored translation"):
                    fixture.state.validate_thinking(["n_thought"], translated=True)

    def test_standalone_thinking_does_not_count_as_a_chronological_append(self):
        self.fixture.node("n_standalone", "thinking", content=CORE + " A standalone thought.")
        self.fixture.edge("e_standalone", "n_standalone", "n_passage", "refines")
        with self.assertRaisesRegex(RuntimeError, "not appended to the current source chain"):
            self.state.validate_thinking(["n_standalone"])
        with self.assertRaisesRegex(RuntimeError, "outside the source chronology"):
            self.state.validate_all()

    def test_round_nodes_follow_sqlite_insertion_order_and_source_membership(self):
        self.fixture.execute("INSERT INTO commits VALUES ('z_first','Earlier','reader','[\"n_passage\"]','[]')")
        baseline = self.state.snapshot()
        self.fixture.node("n_newconcept", "analysis")
        self.fixture.edge("e_grounding", "n_newconcept", "n_passage", "learned_from")
        self.fixture.append_thinking()
        self.fixture.execute("INSERT INTO commits VALUES ('a_later','Later','synthesizer','[\"n_thought\"]','[]')")
        current = self.state.snapshot()
        self.assertEqual([c["id"] for c in current["commits"]], ["z_first", "a_later"])
        self.assertEqual(current["baseline_id"], 2)
        self.assertEqual(self.state.round_nodes({"baseline_node": baseline["baseline_node"]}, current),
                         {"passage_ids": [], "concept_ids": ["n_newconcept"],
                          "thinking_ids": ["n_thought"]})


class IdentityAndSegmentationTests(unittest.TestCase):
    def test_anchor_tolerates_apostrophe_and_line_break_style_but_not_missing_sentences(self):
        prose = CORE.replace("don't", "don’t").replace(". ", ".\n\n") + "\nI notice the opening."
        self.assertIsNone(identity_problem(prose, CORE))
        self.assertIsNotNone(identity_problem(" ".join(CORE.split()[:-5]) + " I notice the opening.", CORE))

    def test_overlong_paragraph_is_read_whole_and_unicode_offsets_match_mcp(self):
        first = "A 🌍 paragraph longer than the tiny target.\n\n"
        second = "A short second paragraph.\n\n"
        third = "Final paragraph with no trailing delimiter."
        text = first + second + third
        self.assertEqual(paragraph_boundaries(text, 3), [
            len(first.encode("utf-16-le")) // 2,
            len((first + second).encode("utf-16-le")) // 2,
            len(text.encode("utf-16-le")) // 2,
        ])

    def test_missing_paragraph_delimiter_produces_one_complete_chunk(self):
        text = "An intact paragraph " * 80
        self.assertEqual(paragraph_boundaries(text, 100), [len(text)])


class RunRecordTests(unittest.TestCase):
    def test_resume_preserves_manifest_and_records_each_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {"source_sha256": "pinned-source", "model": "reading-model",
                        "tool_commit": "local-rc2", "prompts": {"synthesizer": "composed prompt"}}
            RunRecord(directory, manifest)
            manifest_path = Path(directory) / "run_manifest.json"
            original = manifest_path.read_bytes()
            RunRecord(directory, manifest, resume=True)
            self.assertEqual(manifest_path.read_bytes(), original)
            events = [json.loads(line) for line in (Path(directory) / "run_events.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in events], ["invocation", "invocation"])
            self.assertEqual([event["resume"] for event in events], [False, True])

    def test_resume_rejects_changed_source_model_tool_or_composed_prompt(self):
        original = {"source_sha256": "source", "model": "model", "tool_commit": "rc2",
                    "prompts": {"synthesizer": "original"}}
        for key, value in (("source_sha256", "other-source"), ("model", "other-model"),
                           ("tool_commit", "other-build"), ("prompts", {"synthesizer": "changed"})):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                RunRecord(directory, original)
                manifest_path = Path(directory) / "run_manifest.json"
                events_path = Path(directory) / "run_events.jsonl"
                previous_manifest, previous_events = manifest_path.read_bytes(), events_path.read_bytes()
                with self.assertRaisesRegex(ValueError, "Resume configuration changed"):
                    RunRecord(directory, {**original, key: value}, resume=True)
                self.assertEqual(manifest_path.read_bytes(), previous_manifest)
                events = [json.loads(line) for line in events_path.read_text().splitlines()]
                self.assertEqual([event["event"] for event in events],
                                 ["invocation", "invocation", "invocation_rejected"])
                self.assertEqual(events[-1]["changed_fields"], [key])

    def test_unrecorded_legacy_project_cannot_silently_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "recorded run manifest"):
                RunRecord(directory, {"model": "model"}, resume=True)
            self.assertFalse((Path(directory) / "run_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
