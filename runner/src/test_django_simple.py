#!/usr/bin/env python3
"""Simple Django test to debug the issue."""

import json
import requests

# Load Django instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing {instance['instance_id']}")

# Create a minimal patch that should apply
minimal_patch = """diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -1,3 +1,4 @@
+# Test comment
 import ipaddress
 import re
 from pathlib import Path"""

# Test directly with the GCP service
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": minimal_patch,
        "timeout": 60,
        "test_files": ["tests/validators/test_validators.py"]
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

# Now try with empty patch
print("\nTrying with empty patch...")
response = requests.post(
    "http://35.209.45.223:8080/test",
    json={
        "instance_id": instance['instance_id'],
        "patch": "",
        "timeout": 60,
        "test_files": ["tests/validators/test_validators.py"]
    }
)

print(f"Status: {response.status_code}")
result = response.json()
print(f"Duration: {result.get('duration')}s")
print(f"Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")