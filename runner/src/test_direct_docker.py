#!/usr/bin/env python3
"""Test directly with Docker to bypass any issues."""

import subprocess
import json

instance_id = "sympy__sympy-11618"
image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"

print(f"Testing {instance_id} directly with Docker")
print("="*80)

# Load the test patch
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == instance_id:
            instances.append(inst)
            break

instance = instances[0]
test_patch = instance['test_patch']

# Start container
container_name = f"test-{instance_id}"
print(f"\n1. Starting container {container_name}...")
subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
subprocess.run([
    "docker", "run", "-d", "--name", container_name,
    image, "sleep", "3600"
], check=True)

# Apply test patch
print("\n2. Applying test patch...")
proc = subprocess.run(
    ["docker", "exec", "-i", container_name, "bash", "-c", "cd /testbed && git apply -"],
    input=test_patch.encode(),
    capture_output=True
)
if proc.returncode != 0:
    print(f"Patch failed: {proc.stderr.decode()}")
    subprocess.run(["docker", "rm", "-f", container_name])
    exit(1)

# Run the specific test
print("\n3. Running test_issue_11617...")
result = subprocess.run(
    ["docker", "exec", container_name, 
     "conda", "run", "-n", "testbed", "pytest", 
     "sympy/geometry/tests/test_point.py::test_issue_11617", "-v"],
    capture_output=True,
    text=True
)

print(f"Exit code: {result.returncode}")
print("\nSTDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)

# Also try running without specifying the test
print("\n4. Running all tests in test_point.py...")
result2 = subprocess.run(
    ["docker", "exec", container_name,
     "conda", "run", "-n", "testbed", "pytest",
     "sympy/geometry/tests/test_point.py", "-v", "--tb=short"],
    capture_output=True,
    text=True
)
print(f"Exit code: {result2.returncode}")
print(f"Output preview: {result2.stdout[-500:]}")

# Cleanup
subprocess.run(["docker", "rm", "-f", container_name])