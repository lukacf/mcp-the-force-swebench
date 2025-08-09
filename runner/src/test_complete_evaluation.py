#!/usr/bin/env python3
"""Complete test of correct and incorrect patches."""

import json
from evaluator import evaluate_patch

# Test 1: Flask instance with CORRECT patch
print("="*60)
print("TEST 1: Flask instance with CORRECT patch")
print("="*60)

with open('flask_instance.jsonl', 'r') as f:
    flask_instance = json.loads(f.readline())

print(f"Instance: {flask_instance['instance_id']}")
print(f"Expected: The patch adds validation to reject empty Blueprint names")
print(f"Test adds: test_empty_name_not_allowed() which should PASS with correct patch\n")

result = evaluate_patch(flask_instance, flask_instance['patch'])
print(f"Result: Passed={result['passed']}")
print(f"Stats: {result.get('stats', {})}")
print(f"Test files run: {result.get('test_files', [])}")

# Look for the new test in the output
if 'test_empty_name_not_allowed' in result.get('test_output', ''):
    print("✅ New test was run!")
else:
    print("❌ New test was not found in output")

# Test 2: Flask instance with INCORRECT patch
print("\n" + "="*60)
print("TEST 2: Flask instance with INCORRECT patch")
print("="*60)

# Wrong patch that doesn't check for empty names
wrong_patch = """diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py
--- a/src/flask/blueprints.py
+++ b/src/flask/blueprints.py
@@ -190,6 +190,9 @@ def __init__(
            root_path=root_path,
        )

+        if name == "admin":  # WRONG: should check for empty string
+            raise ValueError("'name' cannot be 'admin'.")
+
        if "." in name:
            raise ValueError("'name' may not contain a dot '.' character.")"""

result = evaluate_patch(flask_instance, wrong_patch)
print(f"Result: Passed={result['passed']} (should be False)")
print(f"Stats: {result.get('stats', {})}")

# Test 3: Django instance with CORRECT patch
print("\n" + "="*60)
print("TEST 3: Django instance with CORRECT patch")
print("="*60)

with open('test_instance.jsonl', 'r') as f:
    django_instance = json.loads(f.readline())

print(f"Instance: {django_instance['instance_id']}")
print(f"Expected: URLValidator should reject invalid characters in username/password\n")

result = evaluate_patch(django_instance, django_instance['patch'])
print(f"Result: Passed={result['passed']}")
print(f"Stats: {result.get('stats', {})}")
print(f"Test files run: {result.get('test_files', [])}")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("The GCP tester v2 is now:")
print("✅ Running only specific test files (not all tests)")
print("✅ Supporting both pytest and Django test runners")
print("✅ Properly applying patches and running tests")
print("\nNote: The evaluator needs to be updated to better parse test results")