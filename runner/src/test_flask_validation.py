#\!/usr/bin/env python3
"""Test Flask validation specifically."""

import json
import requests

# Load Flask instance
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == 'pallets__flask-5014':
            break

print("Flask Blueprint Empty Name Validation")
print("="*60)

# Test 1: Just test_patch (should fail)
print("\n1. With test_patch only (bug still exists):")
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": "pallets__flask-5014",
        "patch": inst['test_patch'],
        "timeout": 30,
        "test_files": ["tests/test_blueprints.py::test_empty_name_not_allowed"]
    }
)

result = response.json()
print(f"   Status code: {response.status_code}")
print(f"   Stats: {result.get('passed', 0)} passed, {result.get('failed', 0)} failed")

# Check the actual test result
if 'log_tail' in result:
    if 'FAILED' in result['log_tail'] and 'test_empty_name_not_allowed' in result['log_tail']:
        print("   ✅ CORRECT: Test failed (bug is present)")
    elif 'PASSED' in result['log_tail'] and 'test_empty_name_not_allowed' in result['log_tail']:
        print("   ❌ WRONG: Test passed (bug should be present)")
    else:
        # Show relevant output
        for line in result['log_tail'].split('\\n'):
            if 'test_empty_name' in line or 'FAIL' in line:
                print(f"   {line}")

# Test 2: With full patch (should pass)
print("\n2. With patch + test_patch (bug fixed):")
combined = inst['patch'] + '\n' + inst['test_patch']
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": "pallets__flask-5014",
        "patch": combined,
        "timeout": 30,
        "test_files": ["tests/test_blueprints.py::test_empty_name_not_allowed"]
    }
)

result = response.json()
print(f"   Status code: {response.status_code}")
print(f"   Stats: {result.get('passed', 0)} passed, {result.get('failed', 0)} failed")

if result.get('passed', 0) > 0 and result.get('failed', 0) == 0:
    print("   ✅ CORRECT: Test passed (bug is fixed)")
else:
    print("   ❌ WRONG: Test should pass with fix")
