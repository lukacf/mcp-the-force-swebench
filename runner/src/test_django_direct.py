#!/usr/bin/env python3
"""Test Django label conversion directly."""

import requests
import json

# Test the tester service directly
worker_url = "http://34.44.234.143:8080"

# Test 1: With old label format (should fail)
print("Test 1: Old label format (tests.queries.test_qs_combinators)")
payload1 = {
    "instance_id": "django__django-10554",
    "patch": "",
    "timeout": 30,
    "test_files": ["tests/queries/test_qs_combinators.py"]
}

try:
    response1 = requests.post(f"{worker_url}/test", json=payload1, timeout=35)
    if response1.status_code == 200:
        result1 = response1.json()
        stats = result1.get('stats', result1)
        print(f"Result: {stats.get('passed', 0)} passed, {stats.get('failed', 0)} failed, {stats.get('errors', 0)} errors")
        log_tail = result1.get('log_tail', '')
        if 'RuntimeError' in log_tail:
            print("ERROR: Got RuntimeError about app_label")
        print("\nLog tail:")
        print(log_tail[-800:])
    else:
        print(f"HTTP Error: {response1.status_code}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Check health
print("\n\nTest 2: Health check")
try:
    health = requests.get(f"{worker_url}/health", timeout=5)
    print(f"Health: {health.json()}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Check if conversion is happening by looking at a successful case  
print("\n\nTest 3: Testing django validators (should work)")
payload3 = {
    "instance_id": "django__django-10097",
    "patch": "",
    "timeout": 30,
    "test_files": ["tests/validators/tests.py"]
}

try:
    response3 = requests.post(f"{worker_url}/test", json=payload3, timeout=35)
    if response3.status_code == 200:
        result3 = response3.json()
        print(f"Result: {result3.get('passed', 0)} passed, {result3.get('failed', 0)} failed, {result3.get('errors', 0)} errors")
        # Check log for the actual command run
        log_lines = result3.get('log_tail', '').split('\n')
        for line in log_lines[:10]:
            if 'runtests.py' in line or 'Running' in line:
                print(f"Command line: {line}")
    else:
        print(f"HTTP Error: {response3.status_code}")
except Exception as e:
    print(f"Error: {e}")