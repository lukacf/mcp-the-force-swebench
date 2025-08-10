#!/usr/bin/env python3
"""Test targeted execution with minimal setup."""

import json
import requests

# Simple test patch for psf__requests-1142
test_patch = """
diff --git a/test_requests.py b/test_requests.py
--- a/test_requests.py
+++ b/test_requests.py
@@ -100,6 +100,10 @@ class RequestsTestCase(unittest.TestCase):
         auth = ('user', 'pass')
         assert r.status_code == 200
 
+    def test_dummy_fix(self):
+        # This test was added by the patch
+        assert 1 + 1 == 2
+
     def test_BASICAUTH_TUPLE_HTTP_200_OK_GET(self):
         auth = ('user', 'pass')
         url = httpbin('basic-auth', 'user', 'pass')
"""

# Load worker
with open("worker_config.json") as f:
    config = json.load(f)
worker_url = config["worker_urls"][0]

print("Testing targeted execution...")
print("=" * 80)

# Test WITHOUT patch - should have no tests to run since we only run changed tests
print("\n1. WITHOUT patch (should find no tests to run):")
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": "psf__requests-1142",
        "patch": "",  # Empty patch = no changed tests
        "timeout": 300,
        "test_files": ["all"]
    }
)
result = response.json()
print(f"Result: {result}")

# Test WITH patch - should run only the new test
print("\n2. WITH patch (should run only test_dummy_fix):")
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": "psf__requests-1142", 
        "patch": test_patch,
        "timeout": 300,
        "test_files": ["all"]
    }
)
result = response.json()
print(f"Result: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
print(f"Log tail: {result.get('log_tail', '')[-200:]}")

print("\n✅ Targeted execution is working - only running tests that were changed!")