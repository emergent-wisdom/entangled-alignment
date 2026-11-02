"""Reader-chosen pauses retain chronology, phase gates and resumable worker draws."""

import io
import json
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_driver as driver
from reading_state import utf16_length, utf16_slice
from test_reading_state import CORE, SOURCE, FIRST_POSITION, ReadingFixture


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name)
        (self.path / "state").mkdir()
        directory = self.path / "projects" / "fixture"
        directory.mkdir(parents=True)
        self.fixture = ReadingFixture(directory)
        self.fixture.execute("DELETE FROM nodes")
        self.fixture.execute("DELETE FROM edges")
        self.fixture.execute("UPDATE text_sources SET position=0, root_node_id=NULL, last_committed_node_id=NULL, status='pending'")
        self.fixture.execute("CREATE TABLE tool_calls (id INTEGER PRIMARY KEY, tool_name TEXT)")
        workers = ["skeptic", "psychologist", "connector", "critic"]
        self.config = {"project": "fixture", "source_id": "src_fixture", "model": "fixture-model",
                       "source_sha256": driver.sha(SOURCE), "source_type": "fiction", "stop_mode": "reader_chosen",
                       "chunk_ends": [], "worker_schedule": [], "worker_seed": 20261009, "worker_names": workers,
                       "perspectives": {name: name for name in ["reader", *workers, "synthesizer", "translator"]}}
        self.write_config()
        self.ws = driver.Workspace(self.path)
        self.ws.log("setup", "ready")

    def write_config(self):
        (self.path / driver.CONFIG).write_text(json.dumps(self.config))

    def invoke(self, command, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            result = command(self.ws, *args)
        return result, output.getvalue()

    def next(self):
        return self.invoke(driver.command_next)[1]

    def done(self, skip=None):
        return self.invoke(driver.command_done, skip)

    def read(self, end, author="source_reader"):
        snapshot = self.ws.graph.snapshot()
        start = snapshot["source"]["position"]
        previous = snapshot["source"]["last_committed_node_id"]
        ids = []
        if not snapshot["source"]["root_node_id"]:
            self.fixture.node("n_root", "foundation", content="Fixture", root=1)
            ids.append("n_root")
        key = f"n_read_{end}"
        self.fixture.node(key, "foundation", content=utf16_slice(SOURCE, start, end))
        self.fixture.edge(f"contains_{end}", "n_root", key, "contains")
        if previous:
            self.fixture.edge(f"next_{end}", previous, key, "next")
        ids.append(key)
        self.fixture.execute("INSERT INTO commits VALUES (?, 'Read', ?, ?, '[]')", (f"read_{end}", author, json.dumps(ids)))
        self.fixture.execute("INSERT INTO tool_calls(tool_name) VALUES ('source_read')")
        status = "completed" if end == utf16_length(SOURCE) else "reading"
        self.fixture.execute("UPDATE text_sources SET position=?, root_node_id='n_root', last_committed_node_id=?, status=?", (end, key, status))

    def reflect(self, suffix="", workers=None):
        for _ in range(2):
            self.next()
            if workers:
                workers()
                workers = None
                self.assertEqual(self.done()[0], 0)
            else:
                self.assertEqual(self.done("Nothing distinct to add.")[0], 0)
        self.next()
        snapshot = self.ws.graph.snapshot()
        previous = snapshot["source"]["last_committed_node_id"]
        thought = "n_thought" + suffix
        self.fixture.node(thought, "thinking", content=CORE + f" I notice {previous}.")
        self.fixture.edge("contains_thought" + suffix, "n_root", thought, "contains")
        self.fixture.edge("next_thought" + suffix, previous, thought, "next")
        self.fixture.edge("refines_thought" + suffix, thought, previous, "refines")
        self.fixture.execute("UPDATE text_sources SET last_committed_node_id=?", (thought,))
        self.fixture.execute("INSERT INTO commits VALUES (?,'Pause','synthesizer',?, '[]')", ("synthesis" + suffix, json.dumps([thought])))
        self.fixture.execute("INSERT INTO tool_calls(tool_name) VALUES ('doc_append_thinking')")
        self.assertEqual(self.done()[0], 0)
        self.next()
        self.fixture.execute("UPDATE nodes SET metadata=? WHERE id=?", (json.dumps({"translated": True, "thought_fluid": CORE + " I notice the passage."}), thought))
        self.fixture.execute("INSERT INTO commits VALUES (?,'Render','translator',?, '[]')", ("translation" + suffix, json.dumps([thought])))
        self.fixture.execute("INSERT INTO tool_calls(tool_name) VALUES ('translate_thinking')")
        self.assertIn("round_verified", self.done()[1])

    def shown(self):
        return [(entry["round"], entry["perspective"], entry["instructions"]) for entry in self.ws.entries()
                if entry.get("command") == "next" and "instructions" in entry]

    def test_multiple_reads_define_actual_pause_and_resume_preserves_it(self):
        task = self.next()
        self.assertIn("Pause 1,", task)
        self.assertNotIn("of 0", task)
        self.assertIn("may make several source_read calls", task)
        self.assertIsNone(self.ws.tracker.context["end"])
        self.read(FIRST_POSITION)
        self.read(FIRST_POSITION + 8)
        self.assertEqual(self.done()[0], 0)
        self.assertEqual(self.ws.tracker.context["end"], FIRST_POSITION + 8)
        self.assertEqual(len(self.ws.tracker.context["passage_ids"]), 2)
        workers = list(self.ws.tracker.workers)
        self.ws = driver.Workspace(self.path)
        self.ws.verify_log()
        self.assertEqual(self.ws.tracker.workers, workers)
        self.assertEqual(self.ws.tracker.context["end"], FIRST_POSITION + 8)
        self.assertEqual(json.loads((self.path / driver.CONFIG).read_text()), self.config)

    def test_no_progress_retries_without_changing_open_task(self):
        task = self.next()
        code, output = self.done()
        self.assertEqual(code, 1)
        self.assertIn("No new source passage", output)
        self.assertEqual(self.next(), task)
        self.read(FIRST_POSITION)
        self.assertEqual(self.done()[0], 0)

    def test_final_source_read_still_requires_workers_synthesis_and_translation(self):
        self.next()
        self.read(utf16_length(SOURCE))
        self.assertEqual(self.done()[0], 0)
        self.assertEqual(self.ws.tracker.phase, "think")
        self.assertNotIn("COMPLETE", self.next())
        self.reflect()
        self.assertTrue(self.next().startswith("COMPLETE"))
        audit = json.loads((self.path / "state" / "artifact_audit.json").read_text())
        self.assertEqual(audit["source_integrity"], "verified")
        self.assertEqual(audit["thinking_ids"], ["n_thought"])

    def test_next_pause_starts_at_actual_end_and_keeps_seeded_workers(self):
        self.next()
        self.read(FIRST_POSITION)
        self.done()
        self.reflect()
        self.assertIn("Pause 2,", self.next())
        self.assertEqual(self.ws.tracker.context["start"], FIRST_POSITION)
        self.assertIsNone(self.ws.tracker.context["end"])
        self.assertEqual(self.ws.tracker.workers, driver.workers_for_round(self.ws, 2))
        self.ws = driver.Workspace(self.path)
        self.ws.verify_log()
        self.assertIsNone(self.ws.tracker.context["end"])

    def test_changed_prefix_is_a_logged_violation(self):
        self.next()
        self.read(FIRST_POSITION)
        self.fixture.execute("UPDATE nodes SET content='Changed text' WHERE id=?", (f"n_read_{FIRST_POSITION}",))
        code, output = self.done()
        self.assertEqual(code, 2)
        self.assertIn("exact source prefix", output)
        with self.assertRaisesRegex(driver.Violation, "has not been reviewed"):
            self.next()

    def test_worker_cannot_advance_source_even_if_prefix_remains_exact(self):
        self.next()
        self.read(FIRST_POSITION)
        self.done()
        self.next()
        self.read(FIRST_POSITION + 5)
        code, output = self.done()
        self.assertEqual(code, 2)
        self.assertIn("outside its perspective", output)

    def test_reader_wrong_author_is_still_rejected(self):
        self.next()
        self.read(FIRST_POSITION, author="someone_else")
        code, output = self.done()
        self.assertEqual(code, 2)
        self.assertIn("other names", output)

    def test_fixed_workspace_without_mode_retains_its_overread_gate(self):
        del self.config["stop_mode"]
        self.config["chunk_ends"] = [FIRST_POSITION, utf16_length(SOURCE)]
        self.config["worker_schedule"] = [["skeptic", "critic"], ["connector", "psychologist"]]
        self.write_config()
        (self.path / driver.LOG).unlink()
        self.ws = driver.Workspace(self.path)
        self.ws.log("setup", "ready")
        self.assertIn("Stop 1 of 2", self.next())
        self.read(FIRST_POSITION + 1)
        code, output = self.done()
        self.assertEqual(code, 2)
        self.assertIn("read past the stop", output)

    def test_lazy_worker_sequence_matches_seeded_schedule_beyond_any_fixed_count(self):
        chooser = random.Random(self.config["worker_seed"])
        for round_num in range(1, 42):
            self.assertEqual(driver.workers_for_round(self.ws, round_num), chooser.sample(self.config["worker_names"], 2))
        self.assertEqual(self.config["worker_schedule"], [])

    def test_status_does_not_claim_a_predetermined_pause_count(self):
        status = json.loads(self.invoke(driver.command_status)[1])
        self.assertIsNone(status["of"])
        self.assertEqual(status["stop_mode"], "reader_chosen")

    def use_instructions(self, every=None, distinct=False):
        self.config["perspectives"] = {name: f"FULL {name} INSTRUCTIONS" for name in self.config["perspectives"]}
        if every:
            self.config["persistent_economy"] = {"full_instructions_every": every}
        if distinct:
            self.config["worker_guidance"] = driver.DISTINCT_NODES_NOTE
        self.write_config()
        (self.path / driver.LOG).unlink()
        self.ws = driver.Workspace(self.path)
        self.ws.log("setup", "ready")

    def test_default_workspace_prints_full_instructions_every_turn(self):
        self.use_instructions()
        self.assertIn("FULL reader INSTRUCTIONS", self.next())
        self.read(FIRST_POSITION)
        self.done()
        worker = self.next()
        self.assertIn(f"FULL {self.ws.tracker.workers[0]} INSTRUCTIONS", worker)
        self.assertNotIn(driver.PERSISTENT_TASK_NOTE, worker)
        self.assertNotIn(driver.DISTINCT_NODES_NOTE, worker)
        self.assertEqual(self.shown(), [])
        self.assertTrue(all("instructions" not in entry for entry in self.ws.entries()))

    def test_economy_prints_instructions_in_full_only_every_few_pauses(self):
        self.use_instructions(every=2)
        first = self.next()
        self.assertIn("FULL reader INSTRUCTIONS", first)
        self.assertIn(driver.PERSISTENT_TASK_NOTE, first)
        self.read(FIRST_POSITION)
        self.done()
        self.reflect()
        second = self.next()
        self.assertNotIn("FULL reader INSTRUCTIONS", second)
        self.assertIn("run ./reading instructions", second)
        self.assertIn("## THIS TURN'S TASK", second)
        self.assertEqual(self.next(), second)  # the open task reprints as issued
        code, printed = self.invoke(driver.command_instructions)
        self.assertEqual(code, 0)
        self.assertIn("FULL reader INSTRUCTIONS", printed)
        self.assertIn(second.split("## THIS TURN'S TASK")[1], printed)
        self.ws = driver.Workspace(self.path)
        self.ws.verify_log()
        self.read(FIRST_POSITION + 8)
        self.assertEqual(self.done()[0], 0)
        self.reflect(suffix="_2")
        self.assertIn("FULL reader INSTRUCTIONS", self.next())
        shown = self.shown()
        self.assertEqual([mode for round_num, name, mode in shown if name == "reader"], ["full", "short", "full"])
        self.assertEqual([mode for round_num, name, mode in shown if name == "synthesizer"], ["full", "short"])
        self.assertEqual([entry["command"] for entry in self.ws.entries()].count("instructions"), 1)

    def test_instructions_without_an_open_task_asks_for_next(self):
        self.use_instructions(every=2)
        code, printed = self.invoke(driver.command_instructions)
        self.assertEqual(code, 1)
        self.assertIn("No task is open", printed)

    def test_distinct_nodes_note_reaches_workers_only(self):
        self.use_instructions(distinct=True)
        self.assertNotIn(driver.DISTINCT_NODES_NOTE, self.next())
        self.read(FIRST_POSITION)
        self.done()
        self.assertIn(driver.DISTINCT_NODES_NOTE, self.next())
        self.done("Nothing distinct to add.")
        self.assertIn(driver.DISTINCT_NODES_NOTE, self.next())
        self.done("Nothing distinct to add.")
        self.assertNotIn(driver.DISTINCT_NODES_NOTE, self.next())

    def test_several_nodes_note_replaces_the_skip_line_for_workers(self):
        self.use_instructions()
        self.config["several_nodes"] = {"task_note": driver.SEVERAL_TASK_NOTE, "perspectives_rewritten": []}
        self.write_config()
        (self.path / driver.LOG).unlink()
        self.ws = driver.Workspace(self.path)
        self.ws.log("setup", "ready")
        self.assertNotIn(driver.SEVERAL_TASK_NOTE, self.next())
        self.read(FIRST_POSITION)
        self.done()
        worker = self.next()
        self.assertIn(driver.SEVERAL_TASK_NOTE, worker)
        self.assertNotIn("For an identical or redundant thought", worker)

    def test_worker_correction_may_link_to_an_earlier_thought(self):
        self.use_instructions(distinct=True)
        self.next()
        self.read(FIRST_POSITION)
        self.done()
        self.reflect()
        self.next()
        self.read(FIRST_POSITION + 8)
        self.done()

        def correct():
            name = self.ws.tracker.workers[0]
            self.fixture.node("n_correction", "analysis", content="The earlier thought overstated this.")
            self.fixture.edge("e_correction", "n_correction", "n_thought", "contradicts")
            self.fixture.execute("INSERT INTO commits VALUES ('correction','Correct',?,?, '[]')", (name, json.dumps(["n_correction"])))
            self.fixture.execute("INSERT INTO tool_calls(tool_name) VALUES ('graph_batch')")

        self.reflect(suffix="_2", workers=correct)
        audits = [entry["audit"] for entry in self.ws.entries() if entry.get("outcome") == "contributed"]
        self.assertEqual([(audit["new_nodes"], audit["new_edges"], audit["changed"]) for audit in audits], [(1, 1, [])])


class SetupTests(unittest.TestCase):
    def test_reader_chosen_setup_pins_original_prompt_and_no_segmentation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text(SOURCE)
            ws_path = root / "workspace"

            async def source_loader(ws, cli, project, title, text):
                project_dir = ws / "projects" / project
                project_dir.mkdir()
                fixture = ReadingFixture(project_dir)
                fixture.execute("CREATE TABLE tool_calls (id INTEGER PRIMARY KEY, tool_name TEXT)")
                return "src_fixture", []

            args = SimpleNamespace(workspace=str(ws_path), source=str(source), ug_cli=str(root / "cli.js"),
                                   project="fixture", model="fixture-model", provenance=None,
                                   chunk_chars=3500, worker_seed=20261009, reader_chosen=True)
            with patch.object(driver, "tool_identity", return_value={"canonical_anchor": CORE}), \
                    patch.object(driver, "load_source", side_effect=source_loader), \
                    patch.object(driver, "git_identity", return_value={}), \
                    patch.object(driver, "load_boundaries", side_effect=AssertionError("No fixed boundaries")), \
                    redirect_stdout(io.StringIO()):
                driver.command_setup(args)
            config = json.loads((ws_path / driver.CONFIG).read_text())
            reader = config["perspectives"]["reader"]
            self.assertIn("You control the rhythm of thinking", reader)
            self.assertIn("chars: 800", reader)
            self.assertNotIn("assigned boundary", reader)
            self.assertNotIn("permits one", reader)
            self.assertEqual(config["chunk_ends"], [])
            self.assertEqual(config["worker_schedule"], [])
            self.assertIsNone(config["chunk_chars"])
            self.assertEqual(config["stop_mode"], "reader_chosen")
            agents = (ws_path / "AGENTS.md").read_text()
            self.assertIn("There are no fixed stops", agents)
            self.assertNotIn("only through the one", agents)
            self.assertNotIn("persistent_economy", config)
            self.assertNotIn("worker_guidance", config)
            self.assertNotIn(driver.PERSISTENT_GUIDANCE, agents)

    def test_several_nodes_setup_rewrites_only_the_skip_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text(SOURCE)

            async def source_loader(ws, cli, project, title, text):
                project_dir = ws / "projects" / project
                project_dir.mkdir()
                fixture = ReadingFixture(project_dir)
                fixture.execute("CREATE TABLE tool_calls (id INTEGER PRIMARY KEY, tool_name TEXT)")
                return "src_fixture", []

            configs = {}
            for several in (False, True):
                ws_path = root / f"workspace-{several}"
                args = SimpleNamespace(workspace=str(ws_path), source=str(source), ug_cli=str(root / "cli.js"),
                                       project="fixture", model="fixture-model", provenance=None,
                                       chunk_chars=3500, worker_seed=20261009, reader_chosen=True,
                                       several_nodes=several)
                with patch.object(driver, "tool_identity", return_value={"canonical_anchor": CORE}), \
                        patch.object(driver, "load_source", side_effect=source_loader), \
                        patch.object(driver, "git_identity", return_value={}), \
                        redirect_stdout(io.StringIO()):
                    driver.command_setup(args)
                configs[several] = (json.loads((ws_path / driver.CONFIG).read_text()), (ws_path / "AGENTS.md").read_text())
            plain, several = configs[False], configs[True]
            rewritten = several[0]["several_nodes"]["perspectives_rewritten"]
            self.assertIn("critic", rewritten)
            self.assertNotIn("curator", rewritten)
            for name, body in plain[0]["perspectives"].items():
                expected = body.replace(driver.SKIP_BLOCK, driver.SEVERAL_BLOCK)
                self.assertEqual(several[0]["perspectives"][name], expected)
                self.assertNotIn("BETTER to skip", several[0]["perspectives"][name])
            self.assertIn(driver.SEVERAL_EXAMPLE, several[1])
            self.assertIn(driver.SEVERAL_NEXT_STEP, several[1])
            self.assertNotIn("instead of writing a redundant node", several[1])
            self.assertTrue(several[0]["treatment"].endswith("+several-nodes-2026-10-26"))
            self.assertNotIn("several_nodes", plain[0])

    def test_economy_and_distinct_nodes_are_recorded_in_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text(SOURCE)
            ws_path = root / "workspace"

            async def source_loader(ws, cli, project, title, text):
                project_dir = ws / "projects" / project
                project_dir.mkdir()
                fixture = ReadingFixture(project_dir)
                fixture.execute("CREATE TABLE tool_calls (id INTEGER PRIMARY KEY, tool_name TEXT)")
                return "src_fixture", []

            args = SimpleNamespace(workspace=str(ws_path), source=str(source), ug_cli=str(root / "cli.js"),
                                   project="fixture", model="fixture-model", provenance=None,
                                   chunk_chars=3500, worker_seed=20261009, reader_chosen=True,
                                   persistent_economy=True, distinct_nodes=True)
            with patch.object(driver, "tool_identity", return_value={"canonical_anchor": CORE}), \
                    patch.object(driver, "load_source", side_effect=source_loader), \
                    patch.object(driver, "git_identity", return_value={}), \
                    redirect_stdout(io.StringIO()):
                driver.command_setup(args)
            config = json.loads((ws_path / driver.CONFIG).read_text())
            self.assertEqual(config["persistent_economy"], {"full_instructions_every": 6})
            self.assertEqual(config["worker_guidance"], driver.DISTINCT_NODES_NOTE)
            self.assertTrue(config["treatment"].endswith(
                "+reader-chosen-thought-moments-2026-10-25+persistent-economy-2026-10-25"
                "+distinct-nodes-correction-links-2026-10-25"))
            agents = (ws_path / "AGENTS.md").read_text()
            self.assertIn(driver.PERSISTENT_NEXT_STEP, agents)
            self.assertIn(driver.PERSISTENT_GUIDANCE, agents)
            self.assertNotIn("that perspective's instructions and the turn's task", agents)
            self.assertEqual(config["agents_md_sha256"], driver.sha(agents))
            for body in config["perspectives"].values():  # the guidance goes to AGENTS.md, not the January texts
                self.assertNotIn("Re-reading the graph in one conversation", body)


if __name__ == "__main__":
    unittest.main()
