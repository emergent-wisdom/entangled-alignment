#!/usr/bin/env python3
"""
Analyze understanding graph database statistics.
"""

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


def main():
    project_id = sys.argv[1] if len(sys.argv) > 1 else "metamorphosis"

    script_dir = Path(__file__).parent
    db_path = script_dir.parent.parent / "understanding" / "projects" / project_id / "store.db"

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    print(f"=== Database Statistics: {project_id} ===\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Node statistics
    cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE archived_at IS NULL")
    total_nodes = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE archived_at IS NOT NULL")
    archived_nodes = cursor.fetchone()['count']

    cursor.execute("""
        SELECT trigger, COUNT(*) as count
        FROM nodes
        WHERE archived_at IS NULL
        GROUP BY trigger
        ORDER BY count DESC
    """)
    node_types = cursor.fetchall()

    print(f"NODES: {total_nodes} active, {archived_nodes} archived")
    print("-" * 40)
    for row in node_types:
        pct = (row['count'] / total_nodes * 100) if total_nodes > 0 else 0
        print(f"  {row['trigger'] or 'null':20} {row['count']:5} ({pct:5.1f}%)")

    # Edge statistics
    cursor.execute("SELECT COUNT(*) as count FROM edges")
    total_edges = cursor.fetchone()['count']

    cursor.execute("""
        SELECT type, COUNT(*) as count
        FROM edges
        GROUP BY type
        ORDER BY count DESC
    """)
    edge_types = cursor.fetchall()

    print(f"\nEDGES: {total_edges} total")
    print("-" * 40)
    for row in edge_types:
        pct = (row['count'] / total_edges * 100) if total_edges > 0 else 0
        print(f"  {row['type'] or 'null':20} {row['count']:5} ({pct:5.1f}%)")

    # Commit statistics
    cursor.execute("SELECT COUNT(*) as count FROM commits")
    total_commits = cursor.fetchone()['count']

    cursor.execute("""
        SELECT agent_name, COUNT(*) as count
        FROM commits
        WHERE agent_name IS NOT NULL
        GROUP BY agent_name
        ORDER BY count DESC
    """)
    commits_by_agent = cursor.fetchall()

    print(f"\nCOMMITS: {total_commits} total")
    print("-" * 40)
    for row in commits_by_agent:
        pct = (row['count'] / total_commits * 100) if total_commits > 0 else 0
        print(f"  {row['agent_name']:20} {row['count']:5} ({pct:5.1f}%)")

    # Document structure
    cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE is_doc_root = 1")
    doc_roots = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE file_type IS NOT NULL")
    doc_nodes = cursor.fetchone()['count']

    print(f"\nDOCUMENTS: {doc_roots} roots, {doc_nodes} content nodes")

    # Metadata statistics (for translated nodes, etc.)
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM nodes
        WHERE json_extract(metadata, '$.translated') = 1
    """)
    translated = cursor.fetchone()['count']

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM nodes
        WHERE trigger = 'thinking'
    """)
    thinking_nodes = cursor.fetchone()['count']

    print(f"\nTHINKING NODES: {thinking_nodes} total, {translated} translated")

    # Revision statistics
    cursor.execute("""
        SELECT AVG(version) as avg_version, MAX(version) as max_version
        FROM nodes
        WHERE archived_at IS NULL
    """)
    revision_stats = cursor.fetchone()
    print(f"\nREVISIONS: avg {revision_stats['avg_version']:.1f}, max {revision_stats['max_version']}")

    # Graph connectivity
    cursor.execute("""
        SELECT n.id, n.title, COUNT(e.id) as edge_count
        FROM nodes n
        LEFT JOIN edges e ON n.id = e.from_id OR n.id = e.to_id
        WHERE n.archived_at IS NULL AND n.file_type IS NULL
        GROUP BY n.id
        ORDER BY edge_count DESC
        LIMIT 5
    """)
    most_connected = cursor.fetchall()

    print(f"\nMOST CONNECTED NODES:")
    print("-" * 40)
    for row in most_connected:
        title = (row['title'][:35] + '...') if len(row['title'] or '') > 35 else (row['title'] or 'untitled')
        print(f"  {row['edge_count']:3} edges: {title}")

    # Orphan check (nodes with no edges)
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM nodes n
        WHERE n.archived_at IS NULL
        AND n.file_type IS NULL
        AND n.is_doc_root IS NULL
        AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.from_id = n.id OR e.to_id = n.id)
    """)
    orphans = cursor.fetchone()['count']
    print(f"\nORPHAN NODES (no edges): {orphans}")

    conn.close()


if __name__ == "__main__":
    main()
