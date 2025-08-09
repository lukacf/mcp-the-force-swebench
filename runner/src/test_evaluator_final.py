#!/usr/bin/env python3
"""Final test of correct and incorrect patches through GCP evaluator."""

import json
from evaluator import evaluate_patch

# Load the Flask instance
with open('flask_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']} - {instance['repo']}")
print("="*60)

# Test 1: CORRECT patch (should make the specific test pass)
print("\n1. Testing CORRECT patch from SWE-Bench (should PASS the new test)")
print("   This adds validation to reject empty Blueprint names")
result = evaluate_patch(instance, instance['patch'])
print(f"   Result: Passed={result['passed']}")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")
if result.get('error'):
    print(f"   Error: {result['error']}")

# Test 2: INCORRECT patch - wrong validation
print("\n2. Testing INCORRECT patch (wrong validation logic)")
incorrect_patch = """diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py
--- a/src/flask/blueprints.py
+++ b/src/flask/blueprints.py
@@ -190,6 +190,9 @@ def __init__(
             root_path=root_path,
         )
 
+        if len(name) > 100:  # WRONG: should check for empty, not length > 100
+            raise ValueError("'name' is too long.")
+
         if "." in name:
             raise ValueError("'name' may not contain a dot '.' character.")"""

result = evaluate_patch(instance, incorrect_patch)
print(f"   Result: Passed={result['passed']} (should be False)")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")

# Test 3: NO patch (baseline - should fail the new test)
print("\n3. Testing NO patch (baseline)")
result = evaluate_patch(instance, "")
print(f"   Result: Passed={result['passed']} (should be False)")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")

print("\n" + "="*60)
print("Summary:")
print("- CORRECT patch should pass the new test that checks empty names are rejected")
print("- INCORRECT patch should fail because it doesn't implement the right check")
print("- NO patch should fail because the feature isn't implemented")
print("\nAll evaluation happened on GCP at http://35.209.45.223:8080")