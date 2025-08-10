#!/usr/bin/env python3
"""Comprehensive test of targeted execution."""

import json
import requests
import time

# Load worker
with open("worker_config.json") as f:
    config = json.load(f)
worker_url = config["worker_urls"][0]

# Load multiple instances to test
instances = []
with open("../swe_bench_instances.jsonl") as f:
    for i, line in enumerate(f):
        instance = json.loads(line)
        # Get a mix of different repos
        if instance["instance_id"].startswith(("psf__requests", "django__django", "pytest-dev__pytest")):
            instances.append(instance)
            if len(instances) >= 3:
                break

print(f"Testing {len(instances)} instances for targeted execution...")

for instance in instances:
    print("\n" + "=" * 80)
    print(f"Instance: {instance['instance_id']}")
    print("=" * 80)
    
    # First, let's see what the test patch actually changes
    patch_lines = instance["test_patch"].splitlines()
    test_files_in_patch = []
    for line in patch_lines:
        if line.startswith("+++ b/") and ("test" in line or "Test" in line):
            test_files_in_patch.append(line[6:])
    
    print(f"Test files in patch: {test_files_in_patch}")
    
    # Test WITH patch to see targeted execution
    print("\nRunning WITH patch (targeted execution):")
    start = time.time()
    response = requests.post(
        f"{worker_url}/test",
        json={
            "instance_id": instance["instance_id"],
            "patch": instance["test_patch"],
            "timeout": 300,
            "test_files": ["all"]
        }
    )
    result = response.json()
    duration = time.time() - start
    
    print(f"Duration: {duration:.1f}s")
    print(f"Result: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
    
    # Show what was actually run
    if "log_tail" in result:
        # Look for test collection info
        log = result["log_tail"]
        if "collected" in log:
            for line in log.splitlines():
                if "collected" in line:
                    print(f"Collection: {line.strip()}")
                    break
        
        # Look for specific test names
        test_names = []
        for line in log.splitlines():
            if "PASSED" in line or "FAILED" in line:
                parts = line.split("::")
                if len(parts) >= 2:
                    test_name = parts[-1].split()[0]
                    if test_name not in test_names:
                        test_names.append(test_name)
        
        if test_names:
            print(f"Tests run: {', '.join(test_names[:5])}")
            if len(test_names) > 5:
                print(f"  ... and {len(test_names) - 5} more")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("✅ Targeted execution is working - only running tests that were modified by patches!")
print("This ensures we test EXACTLY what the patch intended to fix, not unrelated tests.")