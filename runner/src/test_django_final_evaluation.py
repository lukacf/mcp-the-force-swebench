#!/usr/bin/env python3
"""Final test of Django evaluation with a real SWE-Bench patch."""

import json
from evaluator import evaluate_patch

# Load Django instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("="*60)
print("DJANGO URL VALIDATOR EVALUATION TEST")
print("="*60)
print(f"Instance: {instance['instance_id']}")
print(f"Problem: URL validator incorrectly accepts multiple @ symbols")
print()

# The actual Django patch that fixes the URL validator issue
django_patch = """diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\\.\\-\\+]*)://'  # scheme is validated separately
-        r'(?:\\S+(?::\\S*)?@)?'  # user:pass authentication
+        r'(?:[^\\s:@/]+(?::[^\\s:@/]*)?@)?'  # user:pass authentication
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\\d{2,5})?'  # port
         r'(?:[/?#][^\\s]*)?'  # resource path
"""

# First test with incorrect patch (should fail)
print("1. Testing with INCORRECT patch (empty patch)...")
result = evaluate_patch(instance, "")
print(f"   Result: {'PASS' if result['passed'] else 'FAIL'} ✓ (Expected: FAIL)")
print(f"   Stats: {result['stats']}")
print()

# Now test with the correct patch
print("2. Testing with CORRECT patch...")
result = evaluate_patch(instance, django_patch)
print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
print(f"   Stats: {result['stats']}")
print(f"   Duration: {result['stats']['duration']}s")

if result['passed']:
    print("\n✅ SUCCESS: Django URL validator patch correctly evaluated!")
else:
    print("\n❌ FAILURE: Something went wrong with evaluation")
    print(f"Error: {result.get('error', 'Unknown error')}")
    if result.get('test_output'):
        print("\nTest output (last 20 lines):")
        lines = result['test_output'].split('\n')
        for line in lines[-20:]:
            print(f"  {line}")

print("\n" + "="*60)
print("EVALUATION COMPLETE")
print("="*60)