#!/usr/bin/env python3
"""Test with a wrong patch that should fail."""

import json
from evaluator import evaluate_patch

with open('flask_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

# Patch that checks for wrong thing (not empty string)
wrong_patch = """diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py
--- a/src/flask/blueprints.py
+++ b/src/flask/blueprints.py
@@ -190,6 +190,9 @@ def __init__(
            root_path=root_path,
        )

+        if len(name) > 100:  # WRONG: should check if name is empty
+            raise ValueError("'name' is too long.")
+
        if "." in name:
            raise ValueError("'name' may not contain a dot '.' character.")"""

print("Testing with WRONG patch (checks length > 100 instead of empty)...")
result = evaluate_patch(instance, wrong_patch)

print(f"\nResult: Passed={result['passed']} (should be False)")
print(f"Stats: {result.get('stats', {})}")

# Check if the test actually failed
if result.get('test_output'):
    if 'test_empty_name_not_allowed FAILED' in result['test_output']:
        print("✅ Correct! The test failed as expected")
    elif 'test_empty_name_not_allowed PASSED' in result['test_output']:
        print("❌ Wrong! The test should have failed")