#!/usr/bin/env python3
"""Test the tester service directly to see what it returns."""

import requests
import json

worker_url = "http://34.44.234.143:8080"

# Load instance
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == 'sympy__sympy-11618':
            instances.append(inst)
            break

instance = instances[0]

# Test with only test_patch (should fail)
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": "sympy__sympy-11618",
        "patch": instance['test_patch'],
        "timeout": 30,
        "test_files": ["sympy/geometry/tests/test_point.py::test_issue_11617"]
    },
    timeout=35
)

print("Response status:", response.status_code)
print("\nFull response:")
result = response.json()
print(json.dumps(result, indent=2))

# Check what's in the response
if 'stats' in result:
    print("\nStats:", result['stats'])
else:
    print("\nDirect values:")
    print(f"  passed: {result.get('passed', 'NOT FOUND')}")
    print(f"  failed: {result.get('failed', 'NOT FOUND')}")
    print(f"  errors: {result.get('errors', 'NOT FOUND')}")

# Check log parsing
log_tail = result.get('log_tail', '')
if '1 failed' in log_tail:
    print("\nLog contains '1 failed' but stats show 0 - parsing bug confirmed!")