#!/usr/bin/env python3
"""Direct test to see raw output."""

import requests
import json

with open('flask_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

# Test with the correct patch
combined_patch = instance['patch'] + "\n" + instance['test_patch']

response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": combined_patch,
        "timeout": 60,
        "test_files": ["tests/test_blueprints.py"]
    }
)

result = response.json()
print("RAW RESULT:")
print(json.dumps(result, indent=2))

# Check the log tail for the actual test results
print("\nLOG TAIL ANALYSIS:")
log_tail = result.get('log_tail', '')
if 'test_empty_name_not_allowed PASSED' in log_tail:
    print("✅ The new test PASSED!")
elif 'test_empty_name_not_allowed FAILED' in log_tail:
    print("❌ The new test FAILED")
    
# Look for pytest summary
if '60 passed' in log_tail:
    print("✅ All 60 tests passed (including the new one)")
elif '59 passed' in log_tail:
    print("❓ Only 59 tests ran (new test might not have been added)")