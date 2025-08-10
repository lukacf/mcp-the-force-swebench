#!/usr/bin/env python3
"""Full test of sympy instance to understand the issue."""

import subprocess
import json

instance_id = "sympy__sympy-11618"
image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"

# Load instance
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == instance_id:
            instances.append(inst)
            break

instance = instances[0]
test_patch = instance['test_patch']
fix_patch = instance['patch']

print(f"Testing {instance_id}")
print(f"Fix patch length: {len(fix_patch)}")
print(f"Test patch length: {len(test_patch)}")
print("="*80)

# Start container
container_name = f"full-test-{instance_id}"
subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
subprocess.run([
    "docker", "run", "-d", "--name", container_name,
    image, "sleep", "3600"
], check=True)

# Install pytest
print("\n1. Installing pytest...")
subprocess.run(
    ["docker", "exec", container_name, "conda", "run", "-n", "testbed", "pip", "install", "pytest"],
    capture_output=True
)

# Apply test patch only
print("\n2. Applying test patch...")
proc = subprocess.run(
    ["docker", "exec", "-i", container_name, "bash", "-c", "cd /testbed && git apply -"],
    input=test_patch.encode(),
    capture_output=True
)
if proc.returncode != 0:
    print(f"Test patch failed: {proc.stderr.decode()}")
else:
    print("Test patch applied successfully")

# Run the specific test (should FAIL)
print("\n3. Running test_issue_11617 (should FAIL without fix)...")
result = subprocess.run(
    ["docker", "exec", "-w", "/testbed", container_name, 
     "conda", "run", "-n", "testbed", "pytest", 
     "sympy/geometry/tests/test_point.py::test_issue_11617", "-v", "--tb=short"],
    capture_output=True,
    text=True
)
print(f"Exit code: {result.returncode}")
if result.returncode == 0:
    print("ERROR: Test PASSED without fix! This shouldn't happen.")
else:
    print("GOOD: Test FAILED as expected")
print("\nOutput:")
print(result.stdout)

# Reset and apply both patches
print("\n4. Resetting and applying both patches...")
subprocess.run(["docker", "exec", container_name, "bash", "-c", "cd /testbed && git reset --hard"], capture_output=True)

# Apply fix patch first
proc = subprocess.run(
    ["docker", "exec", "-i", container_name, "bash", "-c", "cd /testbed && git apply -"],
    input=fix_patch.encode(),
    capture_output=True
)
if proc.returncode != 0:
    print(f"Fix patch failed: {proc.stderr.decode()}")

# Apply test patch
proc = subprocess.run(
    ["docker", "exec", "-i", container_name, "bash", "-c", "cd /testbed && git apply -"],
    input=test_patch.encode(),
    capture_output=True  
)
if proc.returncode != 0:
    print(f"Test patch failed: {proc.stderr.decode()}")

# Run test again (should PASS)
print("\n5. Running test_issue_11617 (should PASS with fix)...")
result2 = subprocess.run(
    ["docker", "exec", "-w", "/testbed", container_name,
     "conda", "run", "-n", "testbed", "pytest",
     "sympy/geometry/tests/test_point.py::test_issue_11617", "-v", "--tb=short"],
    capture_output=True,
    text=True
)
print(f"Exit code: {result2.returncode}")
if result2.returncode == 0:
    print("GOOD: Test PASSED with fix")
else:
    print("ERROR: Test FAILED even with fix!")
print("\nOutput:")
print(result2.stdout)

# Cleanup
subprocess.run(["docker", "rm", "-f", container_name])