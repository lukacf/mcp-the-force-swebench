#!/usr/bin/env python3
"""Check what Django test files exist in the container."""

import subprocess
import json

# Load instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

instance_id = instance['instance_id']
image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"

print("Checking Django test structure...")
print("="*60)

# Start a temporary container
cname = "django-test-check"
subprocess.run(["docker", "rm", "-f", cname], capture_output=True)

subprocess.run([
    "docker", "run", "-d", "--name", cname,
    image, "sleep", "30"
], check=True, capture_output=True)

try:
    # Find the repo directory
    find_repo = subprocess.run(
        f"docker exec {cname} find / -maxdepth 3 -name .git -type d 2>/dev/null | head -1 | xargs dirname",
        shell=True, text=True, capture_output=True
    )
    repo_dir = find_repo.stdout.strip() or "/testbed"
    print(f"Repo directory: {repo_dir}")
    
    # List test directories
    print("\nTest directory structure:")
    list_cmd = f"docker exec {cname} find {repo_dir}/tests -type f -name '*.py' | grep -E 'validator|test' | sort"
    result = subprocess.run(list_cmd, shell=True, text=True, capture_output=True)
    print(result.stdout)
    
    # Check specific paths
    print("\nChecking specific test paths:")
    test_paths = [
        f"{repo_dir}/tests/validators/",
        f"{repo_dir}/tests/validators/tests.py",
        f"{repo_dir}/tests/validators/test_validators.py",
        f"{repo_dir}/tests/validators/__init__.py"
    ]
    
    for path in test_paths:
        check = subprocess.run(
            f"docker exec {cname} test -e {path} && echo 'EXISTS' || echo 'NOT FOUND'",
            shell=True, text=True, capture_output=True
        )
        print(f"  {path}: {check.stdout.strip()}")
    
    # List what's actually in tests/validators/
    print("\nContents of tests/validators/:")
    ls_cmd = f"docker exec {cname} ls -la {repo_dir}/tests/validators/ 2>/dev/null | head -20"
    result = subprocess.run(ls_cmd, shell=True, text=True, capture_output=True)
    print(result.stdout)
    
finally:
    subprocess.run(["docker", "rm", "-f", cname], capture_output=True)

print("\nDone!")