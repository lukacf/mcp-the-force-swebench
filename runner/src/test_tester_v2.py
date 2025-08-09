#!/usr/bin/env python3
"""Test the GCP tester v2 directly to see if it supports test_files."""

import requests
import json

# Test with Flask instance
with open('flask_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

# The test patch adds a test for empty Blueprint names
test_files = ['tests/test_blueprints.py']
combined_patch = instance['patch'] + "\n" + instance['test_patch']

print("Testing GCP tester v2 with specific test files...")
print(f"Instance: {instance['instance_id']}")
print(f"Test files: {test_files}")

# Send request with test_files
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": combined_patch,
        "timeout": 60,
        "test_files": test_files  # This is the key addition
    }
)

print(f"\nResponse status: {response.status_code}")
result = response.json()

# Check if it ran specific tests
if "test_files_run" in result:
    print(f"✅ Tester v2 is running! Test files run: {result['test_files_run']}")
else:
    print("❌ Still running old tester (no test_files_run in response)")

print(f"\nFull result: {json.dumps(result, indent=2)}")