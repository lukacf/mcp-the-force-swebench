#!/usr/bin/env python3
"""Test a specific instance to understand validation behavior."""

import json
import requests
import sys

# Test django__django-10554 which is failing
instance_id = "django__django-10554"
worker_url = "http://34.44.234.143:8080"

# Load the instance
instance = None
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        if data['instance_id'] == instance_id:
            instance = data
            break

if not instance:
    print(f"Instance {instance_id} not found")
    sys.exit(1)

# Extract test files
test_files = []
lines = instance['test_patch'].split('\n')
for line in lines:
    if line.startswith('--- a/') or line.startswith('+++ b/'):
        file_path = line[6:].strip()
        if 'test' in file_path and file_path.endswith('.py'):
            test_files.append(file_path)

print(f"Testing {instance_id}")
print(f"Test files: {test_files}")
print("="*70)

# Test 1: With test_patch only
print("\n1. Testing with test_patch only:")
response1 = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance_id,
        "patch": instance['test_patch'],
        "timeout": 120,
        "test_files": test_files
    },
    timeout=150
)

if response1.status_code == 200:
    result1 = response1.json()
    print(f"Response: {json.dumps(result1, indent=2)}")
    
    # Check if it would be considered "passed"
    test_only_passed = (
        result1.get('failed', 0) == 0 and 
        result1.get('errors', 0) == 0 and
        (result1.get('passed', 0) > 0 or result1.get('collected', 0) > 0)
    )
    print(f"\nWould be considered PASSED: {test_only_passed}")
    print(f"Reason: failed={result1.get('failed', 0)}, errors={result1.get('errors', 0)}, passed={result1.get('passed', 0)}, collected={result1.get('collected', 0)}")
    
print("\n" + "="*70)

# Test 2: With patch + test_patch
print("\n2. Testing with patch + test_patch:")
combined_patch = instance['patch'] + '\n' + instance['test_patch']
response2 = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance_id,
        "patch": combined_patch,
        "timeout": 120,
        "test_files": test_files
    },
    timeout=150
)

if response2.status_code == 200:
    result2 = response2.json()
    print(f"Response: {json.dumps(result2, indent=2)}")
    
    # Check if it would be considered "passed"
    with_fix_passed = (
        result2.get('failed', 0) == 0 and 
        result2.get('errors', 0) == 0 and
        (result2.get('passed', 0) > 0 or result2.get('collected', 0) > 0)
    )
    print(f"\nWould be considered PASSED: {with_fix_passed}")
    print(f"Reason: failed={result2.get('failed', 0)}, errors={result2.get('errors', 0)}, passed={result2.get('passed', 0)}, collected={result2.get('collected', 0)}")

print("\n" + "="*70)
print("\nVALIDATION RESULT:")
if 'test_only_passed' in locals() and 'with_fix_passed' in locals():
    is_valid = not test_only_passed and with_fix_passed
    print(f"Test-only passed: {test_only_passed}")
    print(f"With-fix passed: {with_fix_passed}")
    print(f"Expected pattern (fail→pass): {is_valid}")
    print(f"\nThis instance would be marked as: {'PASSED' if is_valid else 'FAILED'}")
    
    if test_only_passed:
        print("\n⚠️  Test passed without the fix - this causes validation to FAIL")