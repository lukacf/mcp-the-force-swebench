#!/usr/bin/env python3
"""Test that evaluator always uses GCP."""

import json
from evaluator import evaluate_patch

# Load a simple test instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']}")

# Test with empty patch - should fail
print("\n1. Testing empty patch (should fail)...")
result = evaluate_patch(instance, "")
print(f"Result: {result}")

# Test with simple bad patch - should fail
print("\n2. Testing bad patch (should fail)...")
bad_patch = """
diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,1 +1,1 @@
-# original
+# bad change
"""
result = evaluate_patch(instance, bad_patch)
print(f"Result: {result}")

print("\nDone! All requests should have gone to GCP at http://35.209.45.223:8080")