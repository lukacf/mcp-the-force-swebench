#!/usr/bin/env python3
"""Test Django with just the code patch, not test modifications."""

import json
import requests

# Load Django instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("Testing Django URL validator fix")
print("="*60)

# Just the code patch (fixing the regex)
code_patch = """diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\.\-\+]*)://'  # scheme is validated separately
-        r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
+        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\d{2,5})?'  # port
         r'(?:[/?#][^\s]*)?'  # resource path"""

# Test with the code patch
print("\n1. Testing with code patch only...")
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
    print(f"   Status: {response.status_code}")
    print(f"   Duration: {result.get('duration')}s")
    print(f"   Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
    
    # Check if Django tests ran
    if result.get('duration', 0) > 3:
        print("   ✓ Django tests are running!")
else:
    print(f"   Error {response.status_code}: {response.text}")

# Now test without any patch to baseline
print("\n2. Testing without patch (baseline)...")
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'], 
        "patch": "",
        "timeout": 60,
        "test_files": ["tests/validators/test_validators.py"]
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"   Duration: {result.get('duration')}s")
    print(f"   Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")

print("\n" + "="*60)