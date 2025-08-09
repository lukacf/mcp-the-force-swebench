#!/usr/bin/env python3
"""Final test of Django with all fixes."""

import json
import requests

# Load Django instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("="*60)
print("FINAL DJANGO TEST")
print("="*60)
print(f"Instance: {instance['instance_id']}")
print(f"Test files: {instance['test_patch'].split('\\n')[0]}")

# First test without patch to see if dependencies install
print("\n1. Testing without patch (dependency check)...")
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": "",
        "timeout": 60,
        "test_files": ["tests/validators"]
    }
)

result = response.json()
print(f"Status code: {response.status_code}")
print(f"Duration: {result.get('duration', '?')}s")

# Check for pytz error
if 'pytz' in result.get('log_tail', ''):
    print("❌ Still has pytz error")
else:
    print("✅ No pytz error!")

# Now test with the actual patch
print("\n2. Testing with correct patch...")
combined_patch = instance['patch'] + "\n" + instance['test_patch']

response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": combined_patch,
        "timeout": 60,
        "test_files": ["tests/validators"]
    }
)

result = response.json()
print(f"Duration: {result.get('duration', '?')}s")
print(f"Stats: {result.get('passed', 0)} passed, {result.get('failed', 0)} failed, {result.get('errors', 0)} errors")

# Show last few lines of output
print("\nLast few lines of output:")
if result.get('log_tail'):
    lines = result['log_tail'].strip().split('\\n')
    for line in lines[-10:]:
        print(f"  {line}")

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)

if result.get('duration', 0) > 3:
    print("✅ Django tests are running (takes 3+ seconds)")
    print("✅ Dependencies were successfully installed")
    if 'pytz' not in result.get('log_tail', ''):
        print("✅ pytz dependency issue is RESOLVED!")
else:
    print("⚠️  Tests completed too quickly, may have issues")