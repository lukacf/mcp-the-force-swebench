#!/usr/bin/env python3
"""Test with synthetic patches to verify targeted execution."""

import json
import requests

# Load worker
with open("worker_config.json") as f:
    config = json.load(f)
worker_url = config["worker_urls"][0]

# Create a synthetic patch that adds a test
synthetic_patch = """diff --git a/tests/test_example.py b/tests/test_example.py
--- a/tests/test_example.py
+++ b/tests/test_example.py
@@ -10,6 +10,11 @@ class TestExample:
     def test_existing(self):
         assert True
         
+    def test_new_feature(self):
+        # This test was added by the patch
+        from example import new_feature
+        assert new_feature(5) == 10
+        
     def test_another(self):
         assert 1 + 1 == 2
"""

print("Testing synthetic patch with django__django-10097...")
print("=" * 80)

# Test the synthetic patch
response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": "django__django-10097",
        "patch": synthetic_patch,
        "timeout": 300,
        "test_files": ["all"]
    }
)

result = response.json()
print(f"Result: {json.dumps(result, indent=2)}")

# Now test a real astropy instance that we know works
print("\n\nTesting real astropy instance...")
print("=" * 80)

# Load an astropy instance
with open("../swe_bench_instances.jsonl") as f:
    for line in f:
        instance = json.loads(line) 
        if instance["instance_id"] == "astropy__astropy-12907":
            break

# Show part of the test patch
print("Test patch preview:")
for i, line in enumerate(instance["test_patch"].splitlines()[:30]):
    if line.startswith("+++") or line.startswith("@@") or line.startswith("+def"):
        print(line)

response = requests.post(
    f"{worker_url}/test",
    json={
        "instance_id": instance["instance_id"],
        "patch": instance["test_patch"],
        "timeout": 300,
        "test_files": ["all"]
    }
)

result = response.json()
print(f"\nResult summary:")
print(f"- Passed: {result.get('passed', 0)}")
print(f"- Failed: {result.get('failed', 0)}")
print(f"- Errors: {result.get('errors', 0)}")
print(f"- Duration: {result.get('duration', 0)}s")

# Check the log
if result.get('log_tail'):
    lines = result['log_tail'].splitlines()
    for line in lines:
        if "Found" in line and "test" in line:
            print(f"- {line.strip()}")
        if "Running pytest with" in line:
            print(f"- {line.strip()}")