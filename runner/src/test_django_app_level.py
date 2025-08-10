#!/usr/bin/env python3
"""Test running Django tests at app level vs file level."""

import json
import requests

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

print(f"Testing {instance_id}")
print("="*70)

# Test 1: Run at app level (queries)
print("\n1. Testing at app level (queries):")
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance_id,
        "patch": instance['test_patch'],
        "timeout": 120,
        "test_files": ["tests/queries"]  # Just the app, not specific file
    },
    timeout=150
)

if response.status_code == 200:
    result = response.json()
    print(f"Status: {response.status_code}")
    print(f"Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
    if 'log_tail' in result and 'RuntimeError' in result['log_tail']:
        print("Still has RuntimeError")
    else:
        print("No RuntimeError!")
        
# Test 2: Run without specifying test files (let Django figure it out)
print("\n2. Testing without specifying test files:")
response2 = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance_id,
        "patch": instance['test_patch'],
        "timeout": 120
        # No test_files - let it run all tests
    },
    timeout=150
)

if response2.status_code == 200:
    result2 = response2.json()
    print(f"Status: {response2.status_code}")
    print(f"Stats: passed={result2.get('passed', 0)}, failed={result2.get('failed', 0)}, errors={result2.get('errors', 0)}")
    print(f"Duration: {result2.get('duration', 0)}s")
    
# Test 3: Check what test files are in the patch
print("\n3. Test files mentioned in patch:")
lines = instance['test_patch'].split('\n')
for line in lines:
    if line.startswith('diff --git'):
        print(f"  {line}")
    elif line.startswith('+') and 'def test' in line:
        print(f"  New test: {line.strip()}")