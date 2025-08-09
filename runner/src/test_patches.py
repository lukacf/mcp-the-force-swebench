#!/usr/bin/env python3
"""Test correct and incorrect patches through GCP evaluator."""

import json
from evaluator import evaluate_patch

# Load the Django URLValidator instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']}")
print(f"Problem: URLValidator should reject invalid characters in username/password")

# The CORRECT patch from the instance
correct_patch = instance['patch']

# An INCORRECT patch that changes the wrong thing
incorrect_patch = """diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\\.\\-\\+]*)://'  # scheme is validated separately
-        r'(?:\\S+(?::\\S*)?@)?'  # user:pass authentication
+        r'(?:.*@)?'  # user:pass authentication - WRONG: allows anything!
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\\d{2,5})?'  # port
         r'(?:[/?#][^\\s]*)?'  # resource path
"""

# A slightly wrong patch that's too restrictive
too_restrictive_patch = """diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\\.\\-\\+]*)://'  # scheme is validated separately
-        r'(?:\\S+(?::\\S*)?@)?'  # user:pass authentication
+        r'(?:[a-z]+(?::[a-z]*)?@)?'  # user:pass authentication - WRONG: too restrictive
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\\d{2,5})?'  # port
         r'(?:[/?#][^\\s]*)?'  # resource path
"""

print("\n1. Testing CORRECT patch (should PASS)...")
result = evaluate_patch(instance, correct_patch)
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")
print(f"Output tail: {result.get('test_output', '')[-200:]}")

print("\n2. Testing INCORRECT patch that's too permissive (should FAIL)...")
result = evaluate_patch(instance, incorrect_patch)
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")

print("\n3. Testing INCORRECT patch that's too restrictive (should FAIL)...")
result = evaluate_patch(instance, too_restrictive_patch)
print(f"Passed: {result['passed']}")
print(f"Error: {result.get('error', 'None')}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")

print("\nDone! All tests ran on GCP.")