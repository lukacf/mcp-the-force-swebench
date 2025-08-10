#!/usr/bin/env python3
"""Check validation status and diagnose issues."""

import json
import requests
import time
from datetime import datetime

# Load worker config
with open('worker_config.json', 'r') as f:
    config = json.load(f)
    worker_urls = config['worker_urls']

print(f"Checking {len(worker_urls)} workers...")
print("=" * 70)

for i, url in enumerate(worker_urls):
    print(f"\nWorker {i+1}: {url}")
    try:
        # Check health
        health_resp = requests.get(f"{url}/health", timeout=5)
        if health_resp.status_code == 200:
            print(f"  ✓ Health: OK")
        else:
            print(f"  ✗ Health: {health_resp.status_code}")
            
        # Check status
        status_resp = requests.get(f"{url}/status", timeout=5)
        if status_resp.status_code == 200:
            status = status_resp.json()
            print(f"  ✓ Status: {status.get('status', 'unknown')}")
            if 'current_evaluation' in status:
                print(f"    Current: {status['current_evaluation']}")
        else:
            print(f"  ✗ Status: {status_resp.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error: {type(e).__name__}: {str(e)}")

# Check validation log
print("\n" + "=" * 70)
print("Validation Log Analysis:")

import os
if os.path.exists('parallel_validation.log'):
    with open('parallel_validation.log', 'r') as f:
        lines = f.readlines()
    
    if lines:
        first_line = lines[0].strip()
        last_line = lines[-1].strip()
        
        # Extract timestamps
        first_time = first_line.split(' - ')[0]
        last_time = last_line.split(' - ')[0]
        
        print(f"First entry: {first_time}")
        print(f"Last entry:  {last_time}")
        print(f"Total lines: {len(lines)}")
        
        # Count results
        passed = sum(1 for line in lines if 'PASSED' in line)
        failed = sum(1 for line in lines if 'FAILED' in line)
        total = passed + failed
        
        print(f"\nResults:")
        print(f"  Total: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        if total > 0:
            print(f"  Success rate: {passed/total*100:.1f}%")
            
        # Check for errors
        errors = [line for line in lines if 'ERROR' in line or 'Exception' in line]
        if errors:
            print(f"\nErrors found: {len(errors)}")
            for err in errors[:3]:
                print(f"  {err.strip()}")
else:
    print("No validation log found.")