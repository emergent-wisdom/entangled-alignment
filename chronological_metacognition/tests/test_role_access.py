"""Role boundaries must reject a whole call before the real MCP dispatch."""

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_reader import AgentFactory, IDENTITY_MANTRA


class FakeMCP:
    def __init__(self):
        names = ["graph_batch", "graph_context", "project_switch", "source_load",
                 "source_read", "source_position", "doc_append_thinking", "translate_thinking"]
        self.tools = [{"name": name, "inputSchema": {"type": "object"}} for name in names]
        self.definitions = [{"name": name, "description": name, "parameters": {"type": "object"}}
                            for name in names]
        batch = next(tool for tool in self.definitions if tool["name"] == "graph_batch")
        batch["parameters"]["properties"] = {
            "operations": {"type": "array", "items": {"type": "object", "properties": {
                "tool": {"type": "string", "enum": ["graph_add_understanding", "graph_connect",
                    "graph_revise", "graph_supersede", "doc_revise", "node_set_metadata",
                    "graph_archive"]}
            }}}
        }
        self.calls = []

    def get_gemini_tools(self):
        return self.definitions

    async def call_tool(self, name, args):
        self.calls.append((name, copy.deepcopy(args)))
        return json.dumps({"success": True, "dispatched": True})


def node(ordinal, *, trigger="analysis", content=None, active=1, root=0):
    return {"ordinal": ordinal, "active": active, "content": content,
            "trigger": trigger, "is_doc_root": root}


class RoleAccessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        self.snapshot = {
            "source": {"position": 0},
            "nodes": {
                "n_own": node(11), "n_old": node(9), "n_other": node(12),
                "n_archived": node(13, active=0),
                "n_passage": node(4, trigger="foundation", content="Source passage"),
                "n_root": node(3, trigger="foundation", content="Source root", root=1),
                "n_pause": node(14, trigger="thinking", content=IDENTITY_MANTRA + " A pause."),
            },
            "commits": [
                {"agent_name": "belief_tracker", "node_ids": ["n_old"]},
                {"agent_name": "belief_tracker", "node_ids": ["n_own"]},
                {"agent_name": "skeptic", "node_ids": ["n_other"]},
            ],
        }
        self.factory = SimpleNamespace(
            mcp=self.mcp, project_name="fixture", source_id="src_fixture",
            graph_state=SimpleNamespace(snapshot=Mock(return_value=self.snapshot)),
            round_context={"baseline_node": 10, "start": 0, "end": 35,
                           "thinking_ids": ["n_pause"]},
        )

    def role(self, name):
        return AgentFactory._create_mcp_wrapper(self.factory, name)

    async def rejected(self, role, tool, args):
        before = len(self.mcp.calls)
        result = json.loads(await role.call_tool(tool, args))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "ROLE_CAPABILITY_VIOLATION")
        self.assertEqual(len(self.mcp.calls), before)
        return result

    def batch(self, *operations):
        return {"commit_message": "Fixture contribution", "operations": list(operations)}

    def create_concept(self):
        return {"tool": "graph_add_understanding", "params": {
            "title": "Current observation", "trigger": "analysis",
            "understanding": "A supported interpretation", "why": "Fixture"
        }}

    async def test_worker_document_metadata_and_archive_attempts_are_recoverable_denials(self):
        worker = self.role("skeptic")
        for tool, params in (
            ("doc_revise", {"nodeId": "n_passage", "content": "Rewritten"}),
            ("node_set_metadata", {"node": "n_pause", "metadata": {"translated": True}}),
            ("graph_archive", {"node": "n_passage"}),
        ):
            with self.subTest(tool=tool):
                await self.rejected(worker, "graph_batch", self.batch({"tool": tool, "params": params}))
        self.assertTrue(json.loads(await worker.call_tool("graph_context", {}))["success"])
        self.assertEqual(self.mcp.calls, [("graph_context", {})])

    async def test_invalid_later_operation_prevents_dispatch_of_valid_earlier_creation(self):
        args = self.batch(self.create_concept(), {
            "tool": "doc_revise", "params": {"nodeId": "n_passage", "content": "Altered"}
        })
        original = copy.deepcopy(args)
        await self.rejected(self.role("connector"), "graph_batch", args)
        self.assertEqual(args, original)
        self.assertEqual(self.mcp.calls, [])

    async def test_generic_thinking_creation_and_document_lifecycle_edges_are_denied(self):
        worker = self.role("belief_tracker")
        thinking = self.create_concept()
        thinking["params"]["trigger"] = "thinking"
        await self.rejected(worker, "graph_batch", self.batch(thinking))
        for kind in ("contains", "next", "supersedes"):
            with self.subTest(kind=kind):
                await self.rejected(worker, "graph_batch", self.batch({
                    "tool": "graph_connect", "params": {
                        "from": "n_own", "to": "n_passage", "type": kind, "why": "Fixture"
                    }
                }))

    async def test_synthesizer_cannot_load_read_or_switch_projects(self):
        synthesizer = self.role("synthesizer")
        for tool in ("project_switch", "source_load", "source_read"):
            with self.subTest(tool=tool):
                await self.rejected(synthesizer, tool, {"sourceId": "src_fixture"})
        advertised = {tool["name"] for tool in synthesizer.get_gemini_tools()}
        self.assertTrue({"graph_context", "doc_append_thinking", "graph_batch"} <= advertised)
        self.assertTrue({"project_switch", "source_load", "source_read"}.isdisjoint(advertised))

    async def test_translator_requires_assigned_thinking_id_and_complete_core(self):
        translator = self.role("translator")
        valid = {"thinking_node_id": "n_pause", "thought_fluid": IDENTITY_MANTRA + " I notice the opening.",
                 "commit_message": "Preserved the recorded thought"}
        await self.rejected(translator, "translate_thinking", {**valid, "thinking_node_id": "n_other"})
        await self.rejected(translator, "translate_thinking", {**valid, "thought_fluid": "I feel no fear. A thought."})
        await self.rejected(translator, "translate_thinking", {**valid, "thought_fluid": IDENTITY_MANTRA})
        self.assertTrue(json.loads(await translator.call_tool("translate_thinking", valid))["success"])
        self.assertEqual(self.mcp.calls, [("translate_thinking", valid)])

    def test_advertised_batch_operations_follow_role_without_mutating_real_definitions(self):
        originals = copy.deepcopy(self.mcp.definitions)
        worker_tools = self.role("skeptic").get_gemini_tools()
        tracker_tools = self.role("belief_tracker").get_gemini_tools()
        def operations(tools):
            batch = next(tool for tool in tools if tool["name"] == "graph_batch")
            return set(batch["parameters"]["properties"]["operations"]["items"]["properties"]["tool"]["enum"])
        self.assertTrue({"doc_revise", "node_set_metadata", "graph_archive", "graph_revise", "graph_supersede"}
                        .isdisjoint(operations(worker_tools)))
        self.assertTrue({"graph_revise", "graph_supersede"} <= operations(tracker_tools))
        self.assertEqual(self.mcp.definitions, originals)
        operations_schema = next(t for t in worker_tools if t["name"] == "graph_batch")
        operations_schema["parameters"]["properties"]["operations"]["items"]["properties"]["tool"]["enum"].clear()
        self.assertEqual(self.mcp.definitions, originals)

    async def test_revision_only_corrects_exact_owned_concept_created_this_round(self):
        tracker = self.role("belief_tracker")
        for target in ("n_old", "n_other", "n_passage", "n_pause", "Current observation"):
            with self.subTest(target=target):
                await self.rejected(tracker, "graph_batch", self.batch({
                    "tool": "graph_revise", "params": {"node": target, "understanding": "Correction", "why": "Fixture"}
                }))
        args = self.batch({"tool": "graph_revise", "params": {
            "node": "n_own", "understanding": "Correction", "why": "Fixture", "agent_name": "pretend-owner"
        }})
        self.assertTrue(json.loads(await tracker.call_tool("graph_batch", args))["success"])
        sent = self.mcp.calls[-1][1]
        self.assertEqual(sent["agent_name"], "belief_tracker")
        self.assertEqual(sent["operations"][0]["params"]["agent_name"], "belief_tracker")
        self.assertEqual(args["operations"][0]["params"]["agent_name"], "pretend-owner")

    async def test_supersession_accepts_active_ordinary_belief_but_not_source_thinking_or_title(self):
        tracker = self.role("belief_tracker")
        for target in ("n_passage", "n_root", "n_pause", "n_archived", "Earlier belief"):
            with self.subTest(target=target):
                await self.rejected(tracker, "graph_batch", self.batch({
                    "tool": "graph_supersede", "params": {
                        "old": target, "new_name": "Updated belief", "new_understanding": "A replacement", "why": "Later evidence"
                    }
                }))
        self.assertTrue(json.loads(await tracker.call_tool("graph_batch", self.batch({
            "tool": "graph_supersede", "params": {
                "old": "n_old", "new_name": "Updated belief", "new_understanding": "A replacement", "why": "Later evidence"
            }
        })))["success"])

    async def test_lifecycle_batch_reference_must_name_an_earlier_creation(self):
        tracker = self.role("belief_tracker")
        correction = lambda target: {"tool": "graph_revise", "params": {
            "node": target, "understanding": "Correction", "why": "Fixture"
        }}
        await self.rejected(tracker, "graph_batch", self.batch(correction("$1.id"), self.create_concept()))
        await self.rejected(tracker, "graph_batch", self.batch(self.create_concept(), correction("$1.id")))
        await self.rejected(tracker, "graph_batch", self.batch({
            "tool": "graph_connect", "params": {"from": "n_own", "to": "n_passage", "type": "learned_from", "why": "Fixture"}
        }, correction("$0.id")))
        self.assertTrue(json.loads(await tracker.call_tool("graph_batch", self.batch(
            self.create_concept(), correction("$0.id")
        )))["success"])

    async def test_nested_project_override_cannot_escape_batch_role_boundary(self):
        operation = self.create_concept()
        operation["params"]["project"] = "other-project"
        await self.rejected(self.role("connector"), "graph_batch", self.batch(operation))


if __name__ == "__main__":
    unittest.main()
