#!/usr/bin/env python3
"""Final test of the updated GCP evaluator with specific test files."""

import json
from evaluator import evaluate_patch

# Test with Flask instance
with open('flask_instance.jsonl', 'r') as f:
    flask_instance = json.loads(f.readline())

print("Testing Flask instance:", flask_instance['instance_id'])
print("="*60)

# The correct patch should make the new test pass
print("\n1. Testing CORRECT patch (should PASS)")
result = evaluate_patch(flask_instance, flask_instance['patch'])
print(f"   Passed: {result['passed']}")
print(f"   Test files run: {result.get('test_files', [])}")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")
if not result['passed']:
    print(f"   Error: {result.get('error', 'Unknown')}")

# Test with Django instance
with open('test_instance.jsonl', 'r') as f:
    django_instance = json.loads(f.readline())

print("\n\nTesting Django instance:", django_instance['instance_id'])
print("="*60)

print("\n2. Testing CORRECT patch (should PASS)")
result = evaluate_patch(django_instance, django_instance['patch'])
print(f"   Passed: {result['passed']}")
print(f"   Test files run: {result.get('test_files', [])}")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")
if not result['passed']:
    print(f"   Error: {result.get('error', 'Unknown')}")

print("\n\nDone! The updated tester should run only specific test files.")