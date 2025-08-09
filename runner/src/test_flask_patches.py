#!/usr/bin/env python3
"""Test correct and incorrect patches through GCP evaluator with Flask instance."""

import json
from evaluator import evaluate_patch

# Load the Flask instance
with open('flask_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']}")
print(f"Repo: {instance['repo']}")
print(f"Problem: {instance['problem_statement'][:200]}...")

# Extract key info
correct_patch = instance['patch']
test_patch = instance['test_patch']

print(f"\nTest patch modifies: {instance['test_patch'].split('\\n')[0:5]}")

# Create an incorrect patch by making a wrong change
# We'll modify the same file but incorrectly
patch_lines = correct_patch.split('\\n')
file_changed = None
for line in patch_lines:
    if line.startswith('diff --git'):
        file_changed = line.split()[2].replace('a/', '')
        break

incorrect_patch = f"""diff --git a/{file_changed} b/{file_changed}
--- a/{file_changed}
+++ b/{file_changed}
@@ -1,1 +1,1 @@
-# original line
+# This is a wrong change that will break tests
"""

print(f"\n1. Testing CORRECT patch (should PASS)...")
result = evaluate_patch(instance, correct_patch)
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")
print(f"Test files: {result.get('test_files', [])}")

print(f"\n2. Testing INCORRECT patch (should FAIL)...")
result = evaluate_patch(instance, incorrect_patch)
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")

print(f"\n3. Testing EMPTY patch (should FAIL)...")
result = evaluate_patch(instance, "")
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")

print("\nAll tests completed on GCP!")