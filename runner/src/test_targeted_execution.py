#!/usr/bin/env python3
"""Test targeted execution with real SWE-Bench instances."""

import json
import requests
import time
from pathlib import Path

# Load worker config
with open("worker_config.json") as f:
    config = json.load(f)

worker_url = config["worker_urls"][0]

# Load a psf/requests instance
with open("../data/lite/psf__requests-2317.json") as f:
    instance = json.load(f)

# Test 1: WITHOUT patch - should fail
print("=" * 80)
print("TEST 1: Running tests WITHOUT patch (should FAIL)")
print("=" * 80)

response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance["instance_id"],
        "patch": "",  # Empty patch
        "timeout": 300,
        "test_files": ["all"]
    }
)

result_without = response.json()
print(f"Status: {response.status_code}")
print(f"Result: passed={result_without.get('passed', 0)}, failed={result_without.get('failed', 0)}, errors={result_without.get('errors', 0)}")
print(f"Test files run: {result_without.get('test_files_run', [])}")
print(f"Log tail:\n{result_without.get('log_tail', '')[-500:]}")

# Test 2: WITH patch - should pass
print("\n" + "=" * 80)
print("TEST 2: Running tests WITH patch (should PASS)")
print("=" * 80)

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
print(f"Status: {response.status_code}")
print(f"Result: passed={result_with.get('passed', 0)}, failed={result_with.get('failed', 0)}, errors={result_with.get('errors', 0)}")
print(f"Test files run: {result_with.get('test_files_run', [])}")
print(f"Log tail:\n{result_with.get('log_tail', '')[-500:]}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"WITHOUT patch: {result_without.get('failed', 0) + result_without.get('errors', 0)} failures/errors (EXPECTED: >0)")
print(f"WITH patch: {result_with.get('failed', 0) + result_with.get('errors', 0)} failures/errors (EXPECTED: 0)")

# Check if we meet the goal
without_patch_fails = (result_without.get('failed', 0) + result_without.get('errors', 0)) > 0
with_patch_passes = (result_with.get('failed', 0) + result_with.get('errors', 0)) == 0

if without_patch_fails and with_patch_passes:
    print("\n✅ SUCCESS: Tests fail without patch and pass with patch!")
else:
    print("\n❌ FAILURE: Goal not met")
    if not without_patch_fails:
        print("  - Tests should fail WITHOUT patch but didn't")
    if not with_patch_passes:
        print("  - Tests should pass WITH patch but didn't")