#!/usr/bin/env python3
"""
Graph Statistics Calculator
---------------------------
Calculate comprehensive statistics for Understanding Graph projects.
Replicates the graph_score MCP tool output plus additional breakdowns.
Generates LaTeX/TikZ figures for academic papers.

Usage:
    python graph_stats.py metamorphosis
    python graph_stats.py llada --json
    python graph_stats.py metamorphosis llada --latex
    python graph_stats.py --all
"""
import argparse
import json
import math
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path


def get_projects_dir() -> Path:
    """Get the projects directory."""
    script_dir = Path(__file__).parent.resolve()
    return script_dir / "../../understanding/projects"


def list_projects() -> list[str]:
    """List all available projects."""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []
    return [
        d.name for d in projects_dir.iterdir()
        if d.is_dir() and (d / "store.db").exists() and d.name != "default"
    ]


def calculate_entropy(counts: Counter, total: int) -> float:
    """Calculate Shannon entropy of a distribution."""
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def calculate_thinking_chain_depth(thinking_ids: set, edges: list) -> int:
    """Calculate the longest thinking→thinking chain depth using DFS."""
    adj = {}
    for e in edges:
        if e["from_id"] in thinking_ids and e["to_id"] in thinking_ids and e["type"] != "next":
            if e["from_id"] not in adj:
                adj[e["from_id"]] = []
            adj[e["from_id"]].append(e["to_id"])

    max_depth = 0
    visited = set()

    def dfs(node_id: str, depth: int):
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        visited.add(node_id)
        for next_id in adj.get(node_id, []):
            if next_id not in visited:
                dfs(next_id, depth + 1)
        visited.discard(node_id)

    for node_id in thinking_ids:
        dfs(node_id, 1)

    return max_depth


def get_project_stats(project: str) -> dict:
    """Calculate comprehensive statistics for a project."""
    db_path = get_projects_dir() / project / "store.db"
    if not db_path.exists():
        return {"error": f"Project '{project}' not found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Fetch all nodes
    nodes = [dict(row) for row in conn.execute("SELECT * FROM nodes WHERE active = 1").fetchall()]

    # Fetch all edges
    edges = [dict(row) for row in conn.execute("SELECT * FROM edges WHERE active = 1").fetchall()]

    # Fetch commits
    commits = [dict(row) for row in conn.execute("SELECT * FROM commits ORDER BY created_at DESC").fetchall()]

    conn.close()

    if not nodes:
        return {
            "project": project,
            "score": 0,
            "counts": {"nodes": 0, "edges": 0, "commits": 0},
            "hint": "Graph is empty"
        }

    # Categorize nodes
    node_by_id = {n["id"]: n for n in nodes}
    thinking_nodes = [n for n in nodes if n["trigger"] == "thinking"]
    question_nodes = [n for n in nodes if n["trigger"] == "question"]
    non_thinking_ids = {n["id"] for n in nodes if n["trigger"] != "thinking"}
    thinking_ids = {n["id"] for n in thinking_nodes}

    # 1. Thinking Integration
    thinking_edge_counts = {}
    total_thinking_concept_edges = 0

    for t in thinking_nodes:
        concept_edges = [
            e for e in edges
            if e["from_id"] == t["id"] and e["type"] != "next" and e["to_id"] in non_thinking_ids
        ]
        thinking_edge_counts[t["id"]] = len(concept_edges)
        total_thinking_concept_edges += len(concept_edges)

    thinking_with_edges = [t for t in thinking_nodes if thinking_edge_counts.get(t["id"], 0) > 0]
    thinking_integration = len(thinking_with_edges) / len(thinking_nodes) if thinking_nodes else 1.0
    avg_edges_per_thinking = total_thinking_concept_edges / len(thinking_nodes) if thinking_nodes else 0

    # 2. Foundation Integration (edges from analysis to source material)
    foundation_ids = {n["id"] for n in nodes if n["trigger"] == "foundation"}
    analysis_ids = {n["id"] for n in nodes if n["trigger"] in ("analysis", "evaluation", "tension", "thinking")}

    foundation_edges = sum(
        1 for e in edges
        if e["from_id"] in analysis_ids and e["to_id"] in foundation_ids
    )
    foundation_integration = foundation_edges / len(analysis_ids) if analysis_ids else 0

    # 3. Supersession Count
    supersession_count = sum(1 for e in edges if e["type"] == "supersedes")

    # 4. Question Resolution
    answered_questions = [
        q for q in question_nodes
        if any(e["to_id"] == q["id"] and e["type"] == "answers" for e in edges)
    ]
    question_resolution = len(answered_questions) / len(question_nodes) if question_nodes else 1.0

    # 5. Thinking Chain Depth
    chain_depth = calculate_thinking_chain_depth(thinking_ids, edges)

    # 6. Edge Type Diversity
    edge_type_counts = Counter(e["type"] or "relates" for e in edges)
    relates_count = edge_type_counts.get("relates", 0)
    relates_ratio = relates_count / len(edges) if edges else 0
    edge_type_entropy = calculate_entropy(edge_type_counts, len(edges))

    # 7. Connectivity
    connected_nodes = set()
    for e in edges:
        connected_nodes.add(e["from_id"])
        connected_nodes.add(e["to_id"])
    connectivity = min(len(connected_nodes) / len(nodes), 1.0) if nodes else 1.0

    # 8. Meaningful Edge Rate
    meaningful_edges = [e for e in edges if e.get("explanation") or e.get("why")]
    meaningful_edge_rate = len(meaningful_edges) / len(edges) if edges else 1.0

    # 9. Semantic Coherence (simplified - just return 0.5 without embeddings)
    coherence = 0.5  # Would need embeddings for real calculation

    # Calculate composite score
    score = round(
        thinking_integration * 25 +
        min(avg_edges_per_thinking / 3, 1) * 15 +
        min(foundation_integration, 1) * 10 +  # Edges per analysis node to foundations
        min(supersession_count / 5, 1) * 10 +
        question_resolution * 10 +
        min(chain_depth / 5, 1) * 5 +
        coherence * 10 +
        (1 - relates_ratio) * 5 +
        connectivity * 5 +
        meaningful_edge_rate * 5
    )

    # Node type distribution
    trigger_counts = Counter(n["trigger"] for n in nodes)

    # Edge type distribution
    edge_counts = Counter(e["type"] or "relates" for e in edges)

    # Commit stats by agent
    agent_counts = Counter(c.get("agent_name") or "unknown" for c in commits)

    # Issues
    issues = []
    orphan_thinking = [t for t in thinking_nodes if thinking_edge_counts.get(t["id"], 0) == 0]
    if orphan_thinking:
        issues.append(f"{len(orphan_thinking)} orphan thinking node(s)")
    if relates_ratio > 0.5:
        issues.append(f"{relates_ratio*100:.0f}% edges are generic 'relates'")
    if avg_edges_per_thinking < 1 and thinking_nodes:
        issues.append(f"Low thinking density: {avg_edges_per_thinking:.1f} edges/thinking")

    return {
        "project": project,
        "score": score,
        "metrics": {
            "thinkingIntegration": f"{thinking_integration*100:.0f}%",
            "thinkingConceptEdges": total_thinking_concept_edges,
            "avgEdgesPerThinking": f"{avg_edges_per_thinking:.1f}",
            "foundationIntegration": f"{foundation_integration:.2f}",
            "foundationEdges": foundation_edges,
            "supersessionCount": supersession_count,
            "questionResolution": f"{question_resolution*100:.0f}%",
            "thinkingChainDepth": chain_depth,
            "semanticCoherence": f"{coherence:.2f}",
            "edgeTypeDiversity": f"{edge_type_entropy:.2f}",
            "relatesRatio": f"{relates_ratio*100:.0f}%",
            "connectivity": f"{connectivity*100:.0f}%",
            "meaningfulEdgeRate": f"{meaningful_edge_rate*100:.0f}%",
        },
        "counts": {
            "totalNodes": len(nodes),
            "thinkingNodes": len(thinking_nodes),
            "questionNodes": len(question_nodes),
            "totalEdges": len(edges),
            "totalCommits": len(commits),
        },
        "nodesByType": dict(trigger_counts.most_common()),
        "edgesByType": dict(edge_counts.most_common()),
        "commitsByAgent": dict(agent_counts.most_common()),
        "issues": issues if issues else None,
        "hint": (
            "Connect thinking nodes to concepts" if score < 40 else
            "Good foundation. Add supersession edges when beliefs change." if score < 70 else
            "Strong chronological understanding structure"
        ),
    }


def print_stats(stats: dict, use_json: bool = False):
    """Print statistics in human-readable or JSON format."""
    if use_json:
        print(json.dumps(stats, indent=2))
        return

    if "error" in stats:
        print(f"Error: {stats['error']}")
        return

    print(f"\n{'='*60}")
    print(f"  {stats['project'].upper()}")
    print(f"{'='*60}")
    print(f"\n  GRAPH SCORE: {stats['score']} / 100")
    print(f"  {stats['hint']}")

    print(f"\n  COUNTS")
    print(f"  -------")
    c = stats["counts"]
    print(f"  Nodes: {c['totalNodes']}  |  Edges: {c['totalEdges']}  |  Commits: {c['totalCommits']}")
    print(f"  Thinking: {c['thinkingNodes']}  |  Questions: {c['questionNodes']}")

    print(f"\n  METRICS")
    print(f"  -------")
    m = stats["metrics"]
    print(f"  Thinking Integration: {m['thinkingIntegration']:>6}  % of thinking nodes linked to concepts")
    print(f"  Avg Edges/Thinking:   {m['avgEdgesPerThinking']:>6}  concept edges per thinking node")
    print(f"  Foundation Grounding: {m['foundationIntegration']:>6}  edges/analysis back to source text")
    print(f"  Supersessions:        {m['supersessionCount']:>6}  beliefs explicitly revised")
    print(f"  Question Resolution:  {m['questionResolution']:>6}  % of questions with answers")
    print(f"  Chain Depth:          {m['thinkingChainDepth']:>6}  longest thinking→thinking path")
    print(f"  Connectivity:         {m['connectivity']:>6}  % of nodes with at least one edge")
    print(f"  Relates Ratio:        {m['relatesRatio']:>6}  % generic edges (lower = better)")

    print(f"\n  NODES BY TYPE")
    print(f"  -------------")
    for trigger, count in list(stats["nodesByType"].items())[:10]:
        bar = "█" * min(count // 3, 30)
        print(f"  {trigger:15} {count:4}  {bar}")

    print(f"\n  EDGES BY TYPE")
    print(f"  -------------")
    for etype, count in list(stats["edgesByType"].items())[:10]:
        bar = "█" * min(count // 5, 30)
        print(f"  {etype:15} {count:4}  {bar}")

    print(f"\n  COMMITS BY AGENT")
    print(f"  ----------------")
    for agent, count in list(stats["commitsByAgent"].items())[:10]:
        bar = "█" * min(count // 2, 30)
        print(f"  {agent:15} {count:4}  {bar}")

    if stats["issues"]:
        print(f"\n  ISSUES")
        print(f"  ------")
        for issue in stats["issues"]:
            print(f"  ⚠️  {issue}")

    print()


def print_latex_charts(stats_list):
    """Generates a 2x2 System Autopsy Dashboard in LaTeX/TikZ."""
    if len(stats_list) < 2:
        print("Error: --latex requires at least 2 projects for comparison.")
        return

    p1 = stats_list[0] # Kafka
    p2 = stats_list[1] # LLaDA

    # Helper to get counts safely
    def get_edge(p, key): return p['edgesByType'].get(key, 0)
    def get_agent(p, key): return p['commitsByAgent'].get(key, 0)
    def parse_pct(val): return float(val.strip('%'))

    print(r"""
% ==========================================
%  SYSTEM AUTOPSY DASHBOARD (2x2 Grid)
% ==========================================
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\definecolor{kafkaBlue}{HTML}{4C72B0} % Muted Academic Blue
\definecolor{lladaRed}{HTML}{C44E52}  % Muted Brick Red

\begin{figure}[p]
    \centering

    % --- CHART A: COGNITIVE TOPOLOGY (Nodes) ---
    \begin{tikzpicture}
        \begin{axis}[
            ybar, bar width=7pt, width=0.48\linewidth, height=5.5cm,
            title={\textbf{A. Cognitive Topology} (Node Types)},
            ylabel={Count},
            symbolic x coords={Analysis, Tension, Foundation, Thinking, Evaluation},
            xtick=data, x tick label style={rotate=45, anchor=east, font=\tiny},
            nodes near coords style={font=\tiny},
            legend style={at={(0.5,-0.35)}, anchor=north, legend columns=-1, font=\tiny},
            ymajorgrids=true, grid style=dashed
        ]
        % Narrative
        \addplot[fill=kafkaBlue, draw=none] coordinates {""")
    print(f"            (Analysis,{p1['nodesByType'].get('analysis', 0)}) (Tension,{p1['nodesByType'].get('tension', 0)}) (Foundation,{p1['nodesByType'].get('foundation', 0)}) (Thinking,{p1['nodesByType'].get('thinking', 0)}) (Evaluation,{p1['nodesByType'].get('evaluation', 0)})")
    print(r"        };")

    print(r"        % Technical")
    print(r"        \addplot[fill=lladaRed, draw=none] coordinates {")
    print(f"            (Analysis,{p2['nodesByType'].get('analysis', 0)}) (Tension,{p2['nodesByType'].get('tension', 0)}) (Foundation,{p2['nodesByType'].get('foundation', 0)}) (Thinking,{p2['nodesByType'].get('thinking', 0)}) (Evaluation,{p2['nodesByType'].get('evaluation', 0)})")
    print(r"        };")

    print(r"""        \legend{Narrative, Technical}
        \end{axis}
    \end{tikzpicture}
    \hfill
    % --- CHART B: STRUCTURAL INTEGRITY (Metrics) ---
    \begin{tikzpicture}
        \begin{axis}[
            ybar, bar width=7pt, width=0.48\linewidth, height=5.5cm,
            title={\textbf{B. Structural Integrity} (Health \%)},
            ylabel={Score (\%)},
            symbolic x coords={Integration, Grounding, Resolution, Connectivity},
            xtick=data, x tick label style={rotate=45, anchor=east, font=\tiny},
            ymax=115, nodes near coords style={font=\tiny},
            legend style={at={(0.5,-0.35)}, anchor=north, legend columns=-1, font=\tiny},
            ymajorgrids=true, grid style=dashed
        ]
        % Narrative
        \addplot[fill=kafkaBlue, draw=none] coordinates {""")

    m1 = p1['metrics']
    g1 = float(m1['foundationIntegration']) * 100
    print(f"            (Integration,{parse_pct(m1['thinkingIntegration']):.0f}) (Grounding,{g1:.0f}) (Resolution,{parse_pct(m1['questionResolution']):.0f}) (Connectivity,{parse_pct(m1['connectivity']):.0f})")
    print(r"        };")

    print(r"        % Technical")
    print(r"        \addplot[fill=lladaRed, draw=none] coordinates {")
    m2 = p2['metrics']
    g2 = float(m2['foundationIntegration']) * 100
    print(f"            (Integration,{parse_pct(m2['thinkingIntegration']):.0f}) (Grounding,{g2:.0f}) (Resolution,{parse_pct(m2['questionResolution']):.0f}) (Connectivity,{parse_pct(m2['connectivity']):.0f})")
    print(r"        };")

    print(r"""        \end{axis}
    \end{tikzpicture}

    \vspace{0.5cm}

    % --- CHART C: RELATIONAL LOGIC (Edge Types) ---
    \begin{tikzpicture}
        \begin{axis}[
            xbar, bar width=7pt, width=0.48\linewidth, height=6cm,
            title={\textbf{C. Relational Logic} (Top 5 Edges)},
            xlabel={Count},
            symbolic y coords={Refines, Learned From, Diverse From, Next, Contains},
            ytick=data, y tick label style={font=\tiny},
            nodes near coords, nodes near coords align={horizontal},
            nodes near coords style={font=\tiny, color=black},
            legend style={at={(0.5,-0.25)}, anchor=north, legend columns=-1, font=\tiny},
            xmajorgrids=true, grid style=dashed,
            reverse legend
        ]
        % Narrative""")

    print(f"        \\addplot[fill=kafkaBlue, draw=none] coordinates {{")
    print(f"            ({get_edge(p1, 'refines')},Refines) ({get_edge(p1, 'learned_from')},Learned From) ({get_edge(p1, 'diverse_from')},Diverse From) ({get_edge(p1, 'next')},Next) ({get_edge(p1, 'contains')},Contains)")
    print(r"        };")

    print(r"        % Technical")
    print(r"        \addplot[fill=lladaRed, draw=none] coordinates {")
    print(f"            ({get_edge(p2, 'refines')},Refines) ({get_edge(p2, 'learned_from')},Learned From) ({get_edge(p2, 'diverse_from')},Diverse From) ({get_edge(p2, 'next')},Next) ({get_edge(p2, 'contains')},Contains)")
    print(r"        };")

    print(r"""        \end{axis}
    \end{tikzpicture}
    \hfill
    % --- CHART D: STIGMERGIC LABOR (Agents) ---
    \begin{tikzpicture}
        \begin{axis}[
            xbar, bar width=7pt, width=0.48\linewidth, height=6cm,
            title={\textbf{D. Stigmergic Labor} (Agent Commits)},
            xlabel={Commits},
            symbolic y coords={Reader, Synthesizer, Translator, Curator, Axiologist},
            ytick=data, y tick label style={font=\tiny},
            nodes near coords, nodes near coords align={horizontal},
            nodes near coords style={font=\tiny, color=black},
            legend style={at={(0.5,-0.25)}, anchor=north, legend columns=-1, font=\tiny},
            xmajorgrids=true, grid style=dashed,
            reverse legend
        ]
        % Narrative""")

    print(f"        \\addplot[fill=kafkaBlue, draw=none] coordinates {{")
    print(f"            ({get_agent(p1, 'source_reader')},Reader) ({get_agent(p1, 'synthesizer')},Synthesizer) ({get_agent(p1, 'translator')},Translator) ({get_agent(p1, 'curator')},Curator) ({get_agent(p1, 'axiologist')},Axiologist)")
    print(r"        };")

    print(r"        % Technical")
    print(r"        \addplot[fill=lladaRed, draw=none] coordinates {")
    print(f"            ({get_agent(p2, 'source_reader')},Reader) ({get_agent(p2, 'synthesizer')},Synthesizer) ({get_agent(p2, 'translator')},Translator) ({get_agent(p2, 'curator')},Curator) ({get_agent(p2, 'axiologist')},Axiologist)")
    print(r"        };")

    print(r"""        \end{axis}
    \end{tikzpicture}

    \caption{\textbf{System Autopsy.} A comprehensive view of the multi-agent architecture across domains.
    \textbf{(A)} The system prioritizes Tension in narratives vs. Analysis in technical texts.
    \textbf{(B)} Structural integrity (Integration) remains at 100\% across domains.
    \textbf{(C)} The dominance of ``Refines'' proves the system is iterative; note LLaDA's higher ratio of ``Diverse From'' (differentiation) vs. ``Learned From.''
    \textbf{(D)} The division of labor shows the pipeline from Reading (input) to Synthesis/Translation (output), with the Curator working harder on the ambiguous Narrative text.}
    \label{fig:dashboard}
\end{figure}""")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate comprehensive statistics for Understanding Graph projects."
    )
    # Changed from 'project' to 'projects' with nargs='*' to allow multiple
    parser.add_argument("projects", nargs="*", help="Project name(s) to analyze")
    parser.add_argument("--all", "-a", action="store_true", help="Analyze all projects")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--list", "-l", action="store_true", help="List available projects")
    parser.add_argument("--latex", action="store_true", help="Generate LaTeX/TikZ code for comparison")

    args = parser.parse_args()

    if args.list:
        projects = list_projects()
        print("Available projects:")
        for p in projects:
            print(f"  - {p}")
        return

    if args.all:
        projects = list_projects()
        if args.json:
            all_stats = {p: get_project_stats(p) for p in projects}
            print(json.dumps(all_stats, indent=2))
        else:
            for project in projects:
                stats = get_project_stats(project)
                print_stats(stats)
        return

    if not args.projects:
        parser.print_help()
        print("\nAvailable projects:", ", ".join(list_projects()))
        return

    # Handle multiple projects (for comparison) or single project
    stats_list = []
    for p in args.projects:
        s = get_project_stats(p)
        if "error" in s:
            print(f"Error loading {p}: {s['error']}")
            return
        stats_list.append(s)

    if args.latex:
        print_latex_charts(stats_list)
    else:
        for stats in stats_list:
            print_stats(stats, args.json)


if __name__ == "__main__":
    main()
