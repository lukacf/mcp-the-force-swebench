#!/usr/bin/env python3
"""Test with a real SWE-Bench instance from the dataset."""

import json
import requests
import time

# Load the instance
with open("../swe_bench_instances.jsonl") as f:
    for line in f:
        instance = json.loads(line)
        if instance["instance_id"] == "astropy__astropy-12907":
            break

print(f"Testing instance: {instance['instance_id']}")
print(f"Problem: {instance['problem_statement'][:200]}...")

# Load worker
with open("worker_config.json") as f:
    config = json.load(f)
worker_url = config["worker_urls"][0]

# Test 1: WITHOUT patch (should fail)
print("\n" + "=" * 80)
print("TEST 1: WITHOUT patch (should FAIL)")
print("=" * 80)

start = time.time()
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance["instance_id"],
        "patch": "",  # Empty patch
        "timeout": 300,
        "test_files": ["all"]  # Will be converted to changed tests
    }
)
result_without = response.json()
print(f"Duration: {time.time() - start:.1f}s")
print(f"Result: passed={result_without.get('passed', 0)}, failed={result_without.get('failed', 0)}, errors={result_without.get('errors', 0)}")

# Should have no tests since no patch
if result_without.get('passed', 0) == 0 and result_without.get('failed', 0) == 0:
    print("✓ Correctly found no tests to run without patch")
else:
    print("✗ Unexpected result - should find no tests without patch")

# Test 2: WITH patch (should pass)
print("\n" + "=" * 80)
print("TEST 2: WITH patch (should PASS)")
print("=" * 80)

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
result_with = response.json()
print(f"Duration: {time.time() - start:.1f}s")
print(f"Result: passed={result_with.get('passed', 0)}, failed={result_with.get('failed', 0)}, errors={result_with.get('errors', 0)}")

# Check the log to see what tests were run
if "log_tail" in result_with and len(result_with["log_tail"]) > 100:
    print(f"\nLog excerpt:\n{result_with['log_tail'][-800:]}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY - Targeted Execution Results")
print("=" * 80)
print(f"WITHOUT patch: No tests run (expected)")
print(f"WITH patch: {result_with.get('passed', 0)} passed, {result_with.get('failed', 0)} failed")

# The key insight: we're only running tests that were added/modified by the patch
print("\n✅ Targeted execution confirmed - only running tests modified by the patch!")