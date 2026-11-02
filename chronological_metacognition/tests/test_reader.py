import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_reader import (AgentFactory, PhaseTracker, ReadingMCPClient, check_progress,
                        round_contributions, run_reading_session, translation_material)


class FakeGraph:
    source_text = "x"

    def __init__(self, factory):
        self.factory = factory

    def snapshot(self):
        f = self.factory
        return {"source": {"position": int(f.done), "status": "completed" if f.done else "pending", "total_length": 1},
                "baseline_id": 0, "baseline_node": 0, "edges": [], "commits": [],
                "nodes": {"n_thought": {"content": "", "metadata": {"translated": f.translated}}}}

    def chain(self, snapshot):
        return []

    def round_nodes(self, context, snapshot=None):
        return {"passage_ids": ["n_passage"] if self.factory.done else [],
                "concept_ids": [], "thinking_ids": ["n_thought"] if self.factory.synthesized else []}

    def validate_thinking(self, ids, translated=False):
        if translated and not self.factory.translated:
            raise RuntimeError("missing a valid anchored translation")

    def validate_all(self):
        self.validate_thinking(["n_thought"], translated=True)


class FakeAgent:
    def __init__(self, factory, name):
        self.factory, self.name = factory, name
        self.closed = False
        self.message = None

    def kickstart(self, message):
        self.message = message

    async def step(self):
        f = self.factory
        f.calls.append(self.name)
        if self.name == f.fail:
            raise RuntimeError("Interrupted agent")
        if self.name == "reader" and not f.stalled:
            f.done = True
        if self.name == "synthesizer" and not f.omit_synthesis:
            f.synthesized = True
        if self.name == "translator" and not f.omit_translation:
            f.translated = True
        if self.name in {"alpha", "beta"} and not f.omit_worker_finish:
            f.bus.trace_log.append(SimpleNamespace(actor=self.name, event_type="THOUGHT", content="[SKIP] No unique contribution is supported."))

    def close(self):
        self.closed = True


class FakeFactory:
    def __init__(self, done=False, fail=None, stalled=False, synthesized=False,
                 omit_synthesis=False, omit_translation=False, omit_worker_finish=False):
        self.done, self.fail, self.stalled = done, fail, stalled
        self.synthesized, self.translated = synthesized, False
        self.omit_synthesis, self.omit_translation = omit_synthesis, omit_translation
        self.omit_worker_finish = omit_worker_finish
        self.bus = SimpleNamespace(trace_log=[])
        self.calls, self.agents = [], []
        self.graph_state = FakeGraph(self)
        self.chunk_ends = [1]
        self.round_context = {}
        self.record = None
        self.source_id = "src_fixture"
        self.worker_schedule = None

    def get_worker_names(self):
        return ["alpha", "beta"]

    def get_recent_commits(self, **kwargs):
        return []

    def create(self, name):
        agent = FakeAgent(self, name)
        self.agents.append(agent)
        return agent

    async def progress(self):
        return (100, True) if self.done else (0, False)


class ReadingSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.state = Path(self.scratch.name) / "phase_state.json"

    def checkpoint(self, number, phase, read_started=False):
        tracker = PhaseTracker(self.state)
        tracker.save(number, phase)
        tracker.context = {"round": number, "start": 0, "end": 1, "baseline_id": 0, "baseline_node": 0}
        tracker.workers = ["alpha", "beta"]
        tracker.save(number, phase, read_started=read_started)

    async def run_session(self, factory):
        return await run_reading_session(factory, None, factory.progress, round_delay=0, state_file=self.state)

    async def test_final_passage_is_reflected_on_before_completion(self):
        factory = FakeFactory()
        rounds = await self.run_session(factory)
        self.assertEqual(rounds, 1)
        self.assertEqual(factory.calls[0], "reader")
        self.assertEqual(set(factory.calls[1:3]), {"alpha", "beta"})
        self.assertEqual(factory.calls[3:], ["synthesizer", "translator"])
        self.assertFalse(self.state.exists())

    async def test_completed_source_resumes_pending_translation(self):
        self.checkpoint(5, "translate")
        factory = FakeFactory(done=True, synthesized=True)
        self.assertEqual(await self.run_session(factory), 5)
        self.assertEqual(factory.calls, ["translator"])
        self.assertFalse(self.state.exists())

    async def test_interruption_after_final_read_still_runs_reflection(self):
        self.checkpoint(3, "read", read_started=True)
        factory = FakeFactory(done=True)
        self.assertEqual(await self.run_session(factory), 3)
        self.assertNotIn("reader", factory.calls)
        self.assertEqual(set(factory.calls[:2]), {"alpha", "beta"})
        self.assertEqual(factory.calls[2:], ["synthesizer", "translator"])

    async def test_restart_keeps_selected_workers_and_skips_completed_worker(self):
        factory = FakeFactory(fail="beta")
        with patch("run_reader.random.sample", return_value=["alpha", "beta"]):
            with self.assertRaisesRegex(RuntimeError, "Interrupted agent"):
                await self.run_session(factory)
        checkpoint = json.loads(self.state.read_text())
        self.assertEqual(checkpoint["workers"], ["alpha", "beta"])
        self.assertEqual(checkpoint["workers_done"], 1)
        self.assertTrue(all(agent.closed for agent in factory.agents))
        resumed = FakeFactory(done=True)
        with patch("run_reader.random.sample", side_effect=AssertionError("Must not resample")):
            await self.run_session(resumed)
        self.assertEqual(resumed.calls, ["beta", "synthesizer", "translator"])

    async def test_stalled_reader_stops_and_retains_checkpoint(self):
        factory = FakeFactory(stalled=True)
        with self.assertRaisesRegex(RuntimeError, "no progress for 3 rounds"):
            await self.run_session(factory)
        self.assertEqual(factory.calls.count("reader"), 3)
        self.assertEqual(json.loads(self.state.read_text())["phase"], "read")

    async def test_corrupt_checkpoint_is_reported(self):
        self.state.write_text('{"round": 1, "phase": "invalid"}')
        with self.assertRaisesRegex(ValueError, "Invalid reading checkpoint"):
            await self.run_session(FakeFactory())

    async def test_missing_synthesis_retains_round_context(self):
        with self.assertRaisesRegex(RuntimeError, "persisted no thinking"):
            await self.run_session(FakeFactory(omit_synthesis=True))
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["phase"], "synthesize")
        self.assertEqual(saved["context"]["passage_ids"], ["n_passage"])
        self.assertEqual(saved["context"]["baseline_id"], 0)
        self.assertEqual(saved["workers_done"], 2)

    async def test_missing_translation_retains_thinking_ids(self):
        with self.assertRaisesRegex(RuntimeError, "valid anchored translation"):
            await self.run_session(FakeFactory(omit_translation=True))
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["phase"], "translate")
        self.assertEqual(saved["context"]["thinking_ids"], ["n_thought"])
        self.assertTrue(saved["workers"])

    async def test_first_worker_receives_reader_passage_id(self):
        factory = FakeFactory()
        await self.run_session(factory)
        self.assertIn("n_passage", factory.agents[1].message)

    async def test_worker_without_contribution_or_declared_skip_retains_checkpoint(self):
        with self.assertRaisesRegex(RuntimeError, "declared no"):
            await self.run_session(FakeFactory(omit_worker_finish=True))
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["phase"], "think")
        self.assertEqual(saved["workers_done"], 0)



class ToolAndHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_arguments_are_not_renamed_and_defaults_follow_schema(self):
        mcp = ReadingMCPClient("unused", [], default_params={"project": "test", "unknown": "ignored"})
        mcp.tools = [{"name": "example", "inputSchema": {"properties": {"id": {}, "project": {}}}}]
        mcp._send_request = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
        self.assertEqual(await mcp.call_tool("example", {"id": "source"}), "ok")
        self.assertEqual(mcp._send_request.call_args.args[1]["arguments"], {"id": "source", "project": "test"})

    async def test_mcp_error_is_reported(self):
        mcp = ReadingMCPClient("unused", [])
        mcp.tools = [{"name": "example"}]
        mcp._send_request = AsyncMock(return_value={"isError": True, "content": [{"type": "text", "text": "Rejected"}]})
        with self.assertRaisesRegex(RuntimeError, "Rejected"):
            await mcp.call_tool("example", {})

    async def test_progress_failure_is_not_zero_progress(self):
        mcp = type("FakeMCP", (), {"call_tool": AsyncMock(return_value='{"success": false}')})()
        with self.assertRaisesRegex(RuntimeError, "Cannot check source progress"):
            await check_progress(mcp, "source")

    async def test_rounded_percentage_does_not_finish_source_early(self):
        response = json.dumps({"success": True, "percent": 100, "position": 996,
                               "totalLength": 1000, "status": "reading"})
        mcp = type("FakeMCP", (), {"call_tool": AsyncMock(return_value=response)})()
        progress, done = await check_progress(mcp, "source")
        self.assertEqual(progress, 99.6)
        self.assertFalse(done)

    async def test_recent_commits_follow_insertion_order_not_random_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            projects = Path(directory)
            (projects / "test").mkdir()
            with sqlite3.connect(projects / "test" / "store.db") as connection:
                connection.execute("CREATE TABLE commits (id TEXT PRIMARY KEY, message TEXT, agent_name TEXT, node_ids TEXT)")
                connection.executemany("INSERT INTO commits VALUES (?, ?, 'worker', '[]')", [("z", "first"), ("a", "second")])
            factory = AgentFactory(None, None, "unused", None, "source", "test", projects_dir=projects)
            recent = factory.get_recent_commits(after_id=1)
            self.assertEqual([commit["message"] for commit in recent], ["second"])


class MissionMaterialTests(unittest.TestCase):
    def test_round_contributions_keep_complete_worker_text_and_whitespace(self):
        interpretation = "\n\tReported observation.  \n" * 40 + "Uncertain: could the opposite explanation still fit?\n"
        alternative = "  Another reading.\t\n" * 40 + "Open question: whose testimony supports this?\n"
        snapshot = {
            "nodes": {
                "n_interpretation": {"trigger": "thought", "title": "Interpretation",
                                     "understanding": interpretation, "content": None},
                "n_alternative": {"trigger": "question", "title": "Alternative",
                                  "understanding": None, "content": alternative},
                "n_thinking": {"trigger": "thinking", "content": "Excluded thinking block"},
            },
            "commits": [{"node_ids": ["n_interpretation"], "agent_name": "observer"},
                        {"node_ids": ["n_alternative"], "agent_name": "skeptic"}],
            "edges": [{"from_id": "n_alternative", "type": "contradicts", "to_id": "n_interpretation"}],
        }
        message = round_contributions(snapshot, {"concept_ids": list(snapshot["nodes"])})
        self.assertIn(f"- n_interpretation [thought, by observer] Interpretation: {interpretation}", message)
        self.assertIn(f"- n_alternative [question, by skeptic] Alternative: {alternative}", message)
        self.assertIn("n_alternative contradicts n_interpretation", message)
        self.assertNotIn("Excluded thinking block", message)

    def test_translation_material_keeps_old_passages_and_complete_revision_history(self):
        introduction = "First passage.\n"
        old_passage = "\n\tEarlier testimony.  \n" * 60 + "But the witness leaves the cause uncertain.\n"
        current_passage = "  Later observation.\t\n" * 60 + "Could this observation change the earlier reading?\n"
        former = "\n\tFormer interpretation.  \n" * 50 + "Unresolved: perhaps the earlier account was mistaken?\n"
        revised = "  Revised interpretation.\t\n" * 50 + "The alternative remains possible; what would distinguish it?\n"
        nodes = {
            "n_introduction": {"id": "n_introduction", "trigger": "reading", "content": introduction},
            "n_old_passage": {"id": "n_old_passage", "trigger": "reading", "content": old_passage},
            "n_current_passage": {"id": "n_current_passage", "trigger": "reading", "content": current_passage},
            "n_former": {"trigger": "thought", "active": False, "title": "Former",
                         "understanding": None, "content": former},
            "n_revised": {"trigger": "thought", "active": True, "title": "Revised",
                          "understanding": revised, "content": None},
            "n_thinking_old": {"id": "n_thinking_old", "trigger": "thinking", "content": "Earlier reflection"},
            "n_thinking": {"content": "Compare n_revised, n_former, n_old_passage and n_current_passage."},
        }
        snapshot = {
            "nodes": nodes,
            "edges": [{"from_id": "n_revised", "type": "learned_from", "to_id": "n_old_passage"},
                      {"from_id": "n_revised", "type": "supersedes", "to_id": "n_former"}],
        }
        graph = SimpleNamespace(
            source_text=introduction + old_passage + current_passage,
            chain=lambda _: [nodes[key] for key in ("n_introduction", "n_old_passage", "n_thinking_old", "n_current_passage")],
        )
        message = translation_material(graph, snapshot, ["n_thinking"])
        self.assertIn(f"- n_revised [thought, active] Revised: {revised}", message)
        self.assertIn(f"- n_former [thought, replaced] Former: {former}", message)
        self.assertIn(f"    replaces n_former Former: {former}", message)
        self.assertIn(f"    was replaced by n_revised Revised: {revised}", message)
        old_offset = len(introduction)
        current_offset = len(introduction + old_passage)
        total = len(graph.source_text)
        self.assertIn(f"    learned from n_old_passage, the passage at character {old_offset}: \"{old_passage}\"", message)
        self.assertIn(f"- n_old_passage [source passage at character {old_offset} of {total}]: {old_passage}", message)
        self.assertIn(f"- n_current_passage [source passage at character {current_offset} of {total}]: {current_passage}", message)


if __name__ == "__main__":
    unittest.main()
