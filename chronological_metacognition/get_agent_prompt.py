#!/usr/bin/env python3
import sys
import argparse
import os
from pathlib import Path

# Setup paths to import run_reader and swarm
current_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str((current_dir / "../../emergent-swarm/src").resolve()))

try:
    import run_reader
except ImportError:
    print("Error: Could not import run_reader.py. Make sure you are running this script from its directory or that paths are correct.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Get the full system prompt for a specific agent.")
    parser.add_argument("agent", help="Name of the agent (synthesizer, reader, translator, skeptic, curator, etc.)")
    parser.add_argument("--project", default="TEST_PROJECT", help="Project name to inject (default: TEST_PROJECT)")
    parser.add_argument("--source", default="src_TEST_123", help="Source ID to inject (default: src_TEST_123)")
    
    args = parser.parse_args()
    agent_name = args.agent.lower()

    prompt = ""
    
    try:
        if agent_name == "reader":
            prompt = run_reader.make_reader_prompt(args.source, args.project)
        elif agent_name == "synthesizer":
            prompt = run_reader.make_synthesizer_prompt(args.project, args.source)
        elif agent_name == "curator":
            prompt = run_reader.make_curator_prompt(args.project)
        elif agent_name == "translator":
            prompt = run_reader.make_translator_prompt(args.project)
        elif agent_name in run_reader.WORKER_ROLES:
            prompt = run_reader.make_worker_prompt(agent_name, args.project, args.source)
        else:
            print(f"Error: Unknown agent '{agent_name}'.")
            print(f"Available agents: reader, synthesizer, curator, translator, {', '.join(run_reader.WORKER_ROLES.keys())}")
            sys.exit(1)
            
        print(prompt)
        
    except Exception as e:
        print(f"Error generating prompt: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
