#!/usr/bin/env python3
"""Diagnose validation issues by testing specific instances."""

import json
import requests
import sys

def test_single_instance(instance_id, worker_url):
    """Test a single instance to understand the validation behavior."""
    
    # Load the instance
    instance = None
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            data = json.loads(line)
            if data['instance_id'] == instance_id:
                instance = data
                break
    
    if not instance:
        print(f"Instance {instance_id} not found")
        return
    
    print(f"\nTesting instance: {instance_id}")
    print(f"Repository: {instance['repo']}")
    print(f"\nTest patch preview (first 500 chars):")
    print(instance['test_patch'][:500])
    print("\n" + "="*70 + "\n")
    
    # Extract test files
    test_files = []
    lines = instance['test_patch'].split('\n')
    for line in lines:
        if line.startswith('--- a/') or line.startswith('+++ b/'):
            file_path = line[6:].strip()
            if 'test' in file_path and file_path.endswith('.py'):
                test_files.append(file_path)
    
    print(f"Extracted test files: {test_files}")
    
    # Test 1: With test_patch only (should fail)
    print("\n1. Testing with test_patch only (should FAIL):")
    response1 = requests.post(
        f"{worker_url}/test",
        json={
            "instance_id": instance_id,
            "patch": instance['test_patch'],
            "timeout": 120,
            "test_files": test_files
        },
        timeout=150
    )
    
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"   Result: {'PASSED' if result1.get('passed') else 'FAILED'}")
        print(f"   Stats: {result1.get('stats', {})}")
        if 'log_tail' in result1:
            print(f"   Log tail:\n{result1['log_tail'][-500:]}")
    else:
        print(f"   Error: {response1.status_code}")
    
    # Test 2: With patch + test_patch (should pass)
    print("\n2. Testing with patch + test_patch (should PASS):")
    combined_patch = instance['patch'] + '\n' + instance['test_patch']
    response2 = requests.post(
        f"{worker_url}/test",
        json={
            "instance_id": instance_id,
            "patch": combined_patch,
            "timeout": 120,
            "test_files": test_files
        },
        timeout=150
    )
    
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"   Result: {'PASSED' if result2.get('passed') else 'FAILED'}")
        print(f"   Stats: {result2.get('stats', {})}")
        if 'log_tail' in result2:
            print(f"   Log tail:\n{result2['log_tail'][-500:]}")
    else:
        print(f"   Error: {response2.status_code}")
    
    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS:")
    if response1.status_code == 200 and response2.status_code == 200:
        test_only_passed = result1.get('passed', False)
        with_fix_passed = result2.get('passed', False)
        expected_pattern = not test_only_passed and with_fix_passed
        
        print(f"Test-only passed: {test_only_passed}")
        print(f"With-fix passed: {with_fix_passed}")
        print(f"Expected pattern (fail→pass): {expected_pattern}")
        
        if test_only_passed:
            print("\n⚠️  ISSUE: Test passed without the fix! Possible causes:")
            print("   - Test doesn't actually test the bug")
            print("   - Test is checking for existing behavior")
            print("   - Missing test isolation")
        
        if not with_fix_passed:
            print("\n⚠️  ISSUE: Test failed even with the fix! Possible causes:")
            print("   - Fix doesn't actually solve the problem")
            print("   - Test has additional dependencies")
            print("   - Environment setup issues")

if __name__ == '__main__':
    # Test one of the passing instances
    worker_url = "http://34.44.234.143:8080"
    
    # Test a passing instance
    print("Testing a PASSING instance:")
    test_single_instance("django__django-14315", worker_url)
    
    # Test a failing instance
    print("\n\n" + "#"*70 + "\n")
    print("Testing a FAILING instance:")
    test_single_instance("django__django-13212", worker_url)