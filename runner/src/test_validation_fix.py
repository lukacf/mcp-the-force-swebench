#!/usr/bin/env python3
"""
Test the fixed evaluator to verify SWE-Bench validation works correctly.
"""

import json
import requests
from evaluator_fixed import evaluate_patch

# Load a known good instance (Flask empty blueprint name)
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == 'pallets__flask-5063':
            instances.append(inst)
            break

if not instances:
    print("Could not find Flask instance pallets__flask-5063")
    exit(1)

instance = instances[0]
print(f"Testing instance: {instance['instance_id']}")
print(f"This should fix: {instance['problem_statement'][:100]}...")
print("\n" + "="*70 + "\n")

# Test 1: Apply only test_patch (should FAIL - bug exists)
print("1. Testing with test_patch only (should FAIL):")
result1 = evaluate_patch(instance, instance['test_patch'])
print(f"   Result: {'PASSED' if result1['passed'] else 'FAILED'}")
if 'stats' in result1:
    print(f"   Stats: {result1['stats']}")
if result1.get('error'):
    print(f"   Error: {result1['error']}")

print("\n" + "="*70 + "\n")

# Test 2: Apply patch + test_patch (should PASS - bug fixed)
print("2. Testing with patch + test_patch (should PASS):")
combined_patch = instance['patch'] + '\n' + instance['test_patch']
result2 = evaluate_patch(instance, combined_patch)
print(f"   Result: {'PASSED' if result2['passed'] else 'FAILED'}")
if 'stats' in result2:
    print(f"   Stats: {result2['stats']}")
if result2.get('error'):
    print(f"   Error: {result2['error']}")

print("\n" + "="*70 + "\n")

# Validation result
if not result1['passed'] and result2['passed']:
    print("✅ VALIDATION SUCCESSFUL: Test fails without fix, passes with fix")
else:
    print(f"❌ VALIDATION FAILED: Expected fail→pass, got {result1['passed']}→{result2['passed']}")
    
    # Debug info
    if result1['passed']:
        print("\n⚠️  Test passed without the fix - this suggests:")
        print("   - The test might not be testing the bug correctly")
        print("   - Or the bug might already be fixed in the Docker image")
    
    if not result2['passed']:
        print("\n⚠️  Test failed with the fix - this suggests:")
        print("   - The fix might not be correct")
        print("   - Or there might be other test failures")