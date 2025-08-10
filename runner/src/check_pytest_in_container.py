#!/usr/bin/env python3
"""Check pytest installation in container."""

import subprocess

instance_id = "sympy__sympy-11618"
image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"

# Start container
container_name = f"check-{instance_id}"
subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
subprocess.run([
    "docker", "run", "-d", "--name", container_name,
    image, "sleep", "300"
], check=True)

print("Checking pytest installation...")

# Check if pytest exists in testbed env
result = subprocess.run(
    ["docker", "exec", container_name, "conda", "run", "-n", "testbed", "which", "pytest"],
    capture_output=True,
    text=True
)
print(f"\n1. which pytest in testbed env:")
print(f"Exit code: {result.returncode}")
print(f"Output: {result.stdout}")

# Try to install pytest
print("\n2. Installing pytest in testbed env...")
result2 = subprocess.run(
    ["docker", "exec", container_name, "conda", "run", "-n", "testbed", "pip", "install", "pytest"],
    capture_output=True,
    text=True
)
print(f"Exit code: {result2.returncode}")
print(f"Output: {result2.stdout[-500:]}")

# Now check again
result3 = subprocess.run(
    ["docker", "exec", container_name, "conda", "run", "-n", "testbed", "which", "pytest"],
    capture_output=True,
    text=True
)
print(f"\n3. which pytest after install:")
print(f"Exit code: {result3.returncode}")
print(f"Output: {result3.stdout}")

# Now try running the test
print("\n4. Running pytest after install...")
result4 = subprocess.run(
    ["docker", "exec", container_name, "conda", "run", "-n", "testbed", 
     "python", "-m", "pytest", "--version"],
    capture_output=True,
    text=True
)
print(f"Exit code: {result4.returncode}")
print(f"Output: {result4.stdout}")

# Cleanup
subprocess.run(["docker", "rm", "-f", container_name])