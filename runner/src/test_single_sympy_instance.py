#!/usr/bin/env python3
"""Test a single SymPy instance to understand the validation issue."""

import requests
import json

# Test sympy__sympy-11618 directly
worker_url = "http://34.44.234.143:8080"
instance_id = "sympy__sympy-11618"

# Load the instance
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
print("="*80)

# Test 1: Apply ONLY test_patch (should fail if bug exists)
print("\n1. Testing with ONLY test_patch (should FAIL):")
response1 = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance_id,
        "patch": test_patch,  # ONLY the test patch
        "timeout": 30,
        "test_files": ["sympy/geometry/tests/test_point.py::test_issue_11617"]  # Run ONLY the new test
    },
    timeout=35
)

if response1.status_code == 200:
    result1 = response1.json()
    stats1 = result1.get('stats', result1)
    print(f"Response: passed={stats1.get('passed', 0)}, failed={stats1.get('failed', 0)}, errors={stats1.get('errors', 0)}")
    
    # Check log for the specific test
    log_tail = result1.get('log_tail', '')
    if 'test_issue_11617' in log_tail:
        print("\nFound test_issue_11617 in output")
        # Extract relevant lines
        lines = log_tail.split('\n')
        for i, line in enumerate(lines):
            if 'test_issue_11617' in line:
                print(f"  {line}")
                # Show some context
                for j in range(max(0, i-2), min(len(lines), i+5)):
                    if j != i:
                        print(f"  {lines[j]}")
    
    # Check if test was actually collected
    if 'collected' in stats1:
        print(f"\nTests collected: {stats1['collected']}")
    
    print("\nLast 500 chars of log:")
    print(log_tail[-500:])
else:
    print(f"Error: {response1.status_code}")
    print(response1.text[:500])

# Test 2: Run ALL tests in the file to see baseline
print("\n\n2. Testing ALL tests in test_point.py (baseline):")
response2 = requests.post(
    f"{worker_url}/test", 
    json={
        "instance_id": instance_id,
        "patch": "",  # No patch at all
        "timeout": 30,
        "test_files": ["sympy/geometry/tests/test_point.py"]
    },
    timeout=35
)

if response2.status_code == 200:
    result2 = response2.json()
    stats2 = result2.get('stats', result2)
    print(f"Response: passed={stats2.get('passed', 0)}, failed={stats2.get('failed', 0)}, errors={stats2.get('errors', 0)}, collected={stats2.get('collected', 0)}")
else:
    print(f"Error: {response2.status_code}")