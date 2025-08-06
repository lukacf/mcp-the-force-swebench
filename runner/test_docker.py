#!/usr/bin/env python3
"""Test Docker-based SWE-Bench execution with a simple astropy instance."""

import json
import subprocess
import tempfile
from pathlib import Path

# Simple test instance
test_instance = {
    "repo": "astropy/astropy",
    "instance_id": "astropy__astropy-12907",
    "base_commit": "d16bfe05a744909de4b27f5875fe0d4ed41ce607",
    "patch": "dummy patch",
    "test_patch": "dummy test",
    "problem_statement": "Test instance",
    "hints_text": "",
    "created_at": "2022-04-21T00:00:00Z",
    "version": "4.3",
    "FAIL_TO_PASS": ["astropy/modeling/tests/test_separable.py::test_custom_model_separable"],
    "PASS_TO_PASS": [],
    "environment_setup_commit": "1c8dd1f01bb3f3a40d6ad71baf713307b968870a"
}

def main():
    # Create artifacts directory
    artifacts_dir = Path("runner/artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    # Write instance to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_instance, f)
        instance_file = f.name
    
    # Run Docker container
    cmd = [
        "docker", "run", "--rm",
        "--platform", "linux/amd64",  # Force x86_64 on Apple Silicon
        "-v", f"{Path.cwd().absolute()}:/workspace",
        "-v", f"{artifacts_dir.absolute()}:/app/runner/artifacts",
        "-e", f"OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY', '')}",
        "-e", f"ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', '')}",
        "-e", f"XAI_API_KEY={os.environ.get('XAI_API_KEY', '')}",
        "-e", f"VERTEX_PROJECT={os.environ.get('VERTEX_PROJECT', '')}",
        "-e", f"VERTEX_LOCATION={os.environ.get('VERTEX_LOCATION', 'us-central1')}",
        "-w", "/app/runner",
        "swe-bench-worker:latest",
        "python3.11", "-m", "worker",
        "--instance", json.dumps(test_instance),
    ]
    
    print("Running Docker container with command:")
    print(" ".join(cmd))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("\n=== STDOUT ===")
        print(result.stdout)
        print("\n=== STDERR ===")
        print(result.stderr)
        print(f"\n=== EXIT CODE: {result.returncode} ===")
    finally:
        # Clean up
        Path(instance_file).unlink(missing_ok=True)

if __name__ == "__main__":
    import os
    main()