#!/usr/bin/env python3
"""Validate that ground truth patches work as expected."""

import json
import requests
import time

def test_instance(instance_id):
    """Test a single instance with ground truth validation."""
    
    # Load the instance
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            inst = json.loads(line)
            if inst['instance_id'] == instance_id:
                break
        else:
            print(f"Instance {instance_id} not found")
            return
    
    print(f"\nTesting {instance_id}")
    print("="*60)
    print(f"Repository: {inst['repo']}")
    print(f"Base commit: {inst['base_commit'][:12]}...")
    
    # Extract test files
    from evaluator import extract_test_files_from_patch
    test_files = extract_test_files_from_patch(inst['test_patch'])
    print(f"Test files: {test_files}")
    
    # Test 1: Without patch (should fail)
    print("\n1. Testing WITHOUT patch (bug should be present)...")
    response = requests.post(
        "http://35.209.45.223:8080/test",
        json={
            "instance_id": instance_id,
            "patch": "",
            "timeout": 60,
            "test_files": test_files
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   Duration: {result.get('duration')}s")
        print(f"   Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
        without_patch_passed = result.get('passed', 0) > 0 and result.get('failed', 0) == 0 and result.get('errors', 0) == 0
        print(f"   All tests passed: {without_patch_passed} {'❌ (Good - bug present!)' if not without_patch_passed else '⚠️ (Unexpected)'}")
    else:
        print(f"   Error: {response.status_code}")
        return
    
    # Test 2: With ground truth patch (should pass)
    print("\n2. Testing WITH ground truth patch (should fix the bug)...")
    
    # Combine patch and test_patch for full evaluation
    full_patch = inst['patch'] + '\n' + inst['test_patch']
    
    response = requests.post(
        "http://35.209.45.223:8080/test",
        json={
            "instance_id": instance_id,
            "patch": full_patch,
            "timeout": 60,
            "test_files": test_files
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   Duration: {result.get('duration')}s")
        print(f"   Stats: passed={result.get('passed', 0)}, failed={result.get('failed', 0)}, errors={result.get('errors', 0)}")
        with_patch_passed = result.get('passed', 0) > 0 and result.get('failed', 0) == 0 and result.get('errors', 0) == 0
        print(f"   All tests passed: {with_patch_passed} {'✅ (Good - bug fixed!)' if with_patch_passed else '❌ (Problem!)'}")
        
        # Show some output if failed
        if not with_patch_passed and 'log_tail' in result:
            print("\n   Last few lines of output:")
            lines = result['log_tail'].split('\\n')
            for line in lines[-10:]:
                if line.strip():
                    print(f"     {line}")
    else:
        print(f"   Error: {response.status_code}")
        
    # Summary
    print("\n" + "-"*60)
    print("VALIDATION RESULT:")
    if not without_patch_passed and with_patch_passed:
        print("✅ CORRECT: Bug present without patch, fixed with patch")
    else:
        print("❌ ISSUE: Unexpected behavior")
        

# Test a few instances from different repos
test_instances = [
    "django__django-10097",      # We know this works
    "pallets__flask-5014",       # We tested this
    "astropy__astropy-12907",    # First in the file
    "matplotlib__matplotlib-22871",
    "sympy__sympy-13895",
]

print("GROUND TRUTH VALIDATION TEST")
print("="*60)
print("Testing that:")
print("1. Without patch -> Tests FAIL (bug is present)")
print("2. With ground truth patch -> Tests PASS (bug is fixed)")

for instance_id in test_instances:
    test_instance(instance_id)
    time.sleep(2)  # Be nice to the server