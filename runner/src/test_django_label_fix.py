#!/usr/bin/env python3
"""Test Django with the label conversion fix."""

# First test the conversion locally
from sys import path
path.insert(0, '../docker/tester/tester_service')
from tester import convert_to_django_test_labels

test_cases = [
    "tests/validators/",
    "tests/validators",
    "tests/validators/test_ipv4.py",
    "tests/admin_views/",
    "django/core/validators/tests.py"
]

print("Testing Django label conversion:")
print("="*50)
for test in test_cases:
    result = convert_to_django_test_labels([test])
    print(f"{test:30} -> {result[0]}")
print()

# Now test with the actual Django instance
import json
from evaluator import evaluate_patch

with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("Testing Django evaluation with fixed label conversion...")
print("="*50)

# Empty patch to test just the test discovery
result = evaluate_patch(instance, "")
print(f"Result: {'PASS' if result['passed'] else 'FAIL'}")
print(f"Test files: {result.get('test_files', 'Unknown')}")
print(f"Stats: {result.get('stats', {})}")

if not result['passed'] and result.get('test_output'):
    print("\nError output:")
    lines = result['test_output'].split('\n')
    for line in lines[-10:]:
        if line.strip():
            print(f"  {line}")