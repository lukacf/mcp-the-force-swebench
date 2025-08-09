#!/usr/bin/env python3
"""Test Django with properly formatted patch."""

import json
import requests

# Load Django instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("Testing Django URL validator fix")
print("="*60)

# Properly formatted patch with correct escaping
code_patch = r"""diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\.\-\+]*)://'  # scheme is validated separately
-        r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
+        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\d{2,5})?'  # port
         r'(?:[/?#][^\s]*)?'  # resource path
"""

# Test with the code patch
print("\n1. Testing with URL validator fix...")
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": code_patch,
        "timeout": 60,
        "test_files": ["tests/validators/test_validators.py"]
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"   Status: SUCCESS")
    print(f"   Duration: {result.get('duration')}s")
    print(f"   Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
    
    # Show some output
    if 'log_tail' in result:
        lines = result['log_tail'].split('\\n')[-5:]
        print("   Last few lines:")
        for line in lines:
            print(f"     {line}")
else:
    print(f"   Error {response.status_code}: {response.text}")

# Now use the evaluator module
print("\n2. Testing with evaluator.evaluate_patch()...")
from evaluator import evaluate_patch

result = evaluate_patch(instance, code_patch)
print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
if 'stats' in result:
    print(f"   Stats: {result['stats']}")
print(f"   Test files: {result.get('test_files', 'Unknown')}")

print("\n" + "="*60)
print("CONCLUSION:")
if result.get('passed'):
    print("✅ Django URL validator patch is working correctly!")
else:
    print("❌ Django evaluation has issues")
    print(f"   Error: {result.get('error', 'Unknown')}")