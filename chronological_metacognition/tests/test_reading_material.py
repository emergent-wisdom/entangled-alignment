import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_reader import (IDENTITY_MANTRA, AgentFactory, RestrictedMCP, artifact_problem,
                        persistent_shared_blocks, round_contributions, translation_material)


class ArtifactTests(unittest.IsolatedAsyncioTestCase):
    def test_refuses_january_artifacts_and_accepts_plain_prose(self):
        for text in ("He said &quot;no&quot;.", 'He said \\"no\\".', "A thought.\n\n(title: The Glass Fortress)"):
            self.assertIsNotNone(artifact_problem(IDENTITY_MANTRA + " " + text), text)
        self.assertIsNone(artifact_problem(IDENTITY_MANTRA + " He said “no” & left; it’s plain prose."))

    async def test_wrapper_refuses_an_artifact_before_dispatch(self):
        real = Mock(tools=[{"name": "translate_thinking", "inputSchema": {}}], call_tool=AsyncMock())
        wrapper = RestrictedMCP(real, allowed_tools=["translate_thinking"], agent_name="translator")
        reply = json.loads(await wrapper.call_tool("translate_thinking", {
            "thinking_node_id": "n_x", "thought_fluid": IDENTITY_MANTRA + " She said &quot;wait&quot;."}))
        self.assertFalse(reply["success"])
        self.assertIn("HTML entities", reply["message"])
        real.call_tool.assert_not_awaited()


class MissionMaterialTests(unittest.TestCase):
    def test_round_contributions_mark_disagreements_and_authors(self):
        snapshot = {"nodes": {"n_a": {"trigger": "analysis", "title": "Care as territory", "understanding": "A harsh reading."},
                              "n_b": {"trigger": "tension", "title": "Inheriting the burden", "understanding": "A kinder reading."}},
                    "edges": [{"from_id": "n_b", "to_id": "n_a", "type": "contradicts"}],
                    "commits": [{"agent_name": "skeptic", "node_ids": ["n_a"]}, {"agent_name": "critic", "node_ids": ["n_b"]}]}
        text = round_contributions(snapshot, {"concept_ids": ["n_a", "n_b"]})
        for part in ("n_a [analysis, by skeptic]", "n_b [tension, by critic]", "n_b contradicts n_a"):
            self.assertIn(part, text)
        self.assertIn("committed no concepts", round_contributions({"nodes": {}, "edges": [], "commits": []}, {"concept_ids": []}))

    def test_translation_material_reaches_back_with_passage_and_revision_history(self):
        passages = [{"id": "n_p1", "trigger": "foundation", "content": "AAAA"},
                    {"id": "n_t0", "trigger": "thinking", "content": "earlier thought"},
                    {"id": "n_p2", "trigger": "foundation", "content": "BBBB"}]
        nodes = {node["id"]: node for node in passages}
        nodes.update({
            "n_t1": {"id": "n_t1", "trigger": "thinking", "content": IDENTITY_MANTRA + " I recall n_c1 and n_p2."},
            "n_c1": {"id": "n_c1", "trigger": "analysis", "active": 1, "title": "Early reading", "understanding": "From page one."},
            "n_old": {"id": "n_old", "trigger": "analysis", "active": 0, "title": "First guess", "understanding": "Since replaced."},
        })
        snapshot = {"nodes": nodes, "edges": [
            {"from_id": "n_c1", "to_id": "n_p1", "type": "learned_from"},
            {"from_id": "n_c1", "to_id": "n_old", "type": "supersedes"}]}
        graph = SimpleNamespace(chain=lambda _: passages, source_text="AAAABBBB")
        text = translation_material(graph, snapshot, ["n_t1"])
        for part in ("n_c1 [analysis, active] Early reading", "learned from n_p1, the passage at character 0",
                     "replaces n_old First guess: Since replaced.", "n_p2 [source passage at character 4 of 8]"):
            self.assertIn(part, text)


class PersistentPromptTests(unittest.TestCase):
    def factory(self):
        factory = AgentFactory.__new__(AgentFactory)
        factory.source_id, factory.project_name = "src_fixture", "fixture"
        factory.fresh_reading, factory.single_agent, factory.source_type = True, False, "fiction"
        return factory

    def test_split_moves_shared_blocks_once_and_loses_no_line(self):
        factory = self.factory()
        system, instructions = factory.persistent_prompts()
        composed = factory.prompts()
        self.assertEqual(set(instructions), set(factory.perspectives()))
        for block in persistent_shared_blocks(True):
            self.assertEqual(system.count(block), 1)
        for name, text in instructions.items():
            for block in persistent_shared_blocks(True):
                self.assertNotIn(block, text, name)
            lost = [line for line in composed[name].splitlines() if line.strip() and line not in system and line not in text]
            self.assertEqual(lost, [], name)


if __name__ == "__main__":
    unittest.main()
