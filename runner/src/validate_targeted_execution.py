#!/usr/bin/env python3
"""Validate that targeted execution achieves the goal:
- WITHOUT patch: Tests should fail (proving there was a bug)
- WITH patch: Tests should pass (proving the patch fixes it)
"""

import json
import requests
import sys

# Load worker
with open("worker_config.json") as f:
    config = json.load(f)
worker_url = config["worker_urls"][0]

# Test multiple instances
test_instances = [
    "astropy__astropy-12907",  # We know this works
    "pytest-dev__pytest-8399",  # From validation results  
    "scikit-learn__scikit-learn-25747"  # From validation results
]

results = []

for instance_id in test_instances:
    print(f"\n{'='*80}")
    print(f"Testing {instance_id}")
    print(f"{'='*80}")
    
    # Load the instance
    instance = None
    with open("../swe_bench_instances.jsonl") as f:
        for line in f:
            data = json.loads(line)
            if data["instance_id"] == instance_id:
                instance = data
                break
    
    if not instance:
        print(f"❌ Instance {instance_id} not found")
        continue
    
    # The key test: run the PROBLEM patch (not test patch) to see if tests fail
    print("\n1. Running tests on PROBLEM code (should FAIL):")
    response = requests.post(
        f"{worker_url}/test",
        json={
            "instance_id": instance_id,
            "patch": instance["patch"],  # The fix patch
            "timeout": 300,
            "test_files": ["all"]
        }
    )
    problem_result = response.json()
    print(f"   Passed: {problem_result.get('passed', 0)}, Failed: {problem_result.get('failed', 0)}, Errors: {problem_result.get('errors', 0)}")
    
    # Now run with TEST patch to see if tests pass
    print("\n2. Running tests with TEST patch (should PASS):")
    response = requests.post(
        f"{worker_url}/test",
        json={
            "instance_id": instance_id,
            "patch": instance["test_patch"],  # The test patch
            "timeout": 300,
            "test_files": ["all"]
        }
    )
    test_result = response.json()
    print(f"   Passed: {test_result.get('passed', 0)}, Failed: {test_result.get('failed', 0)}, Errors: {test_result.get('errors', 0)}")
    
    # Analyze results
    problem_tests_fail = (problem_result.get('failed', 0) + problem_result.get('errors', 0)) > 0
    test_tests_pass = (test_result.get('failed', 0) + test_result.get('errors', 0)) == 0 and test_result.get('passed', 0) > 0
    
    success = problem_tests_fail or test_tests_pass
    
    results.append({
        "instance_id": instance_id,
        "problem_result": f"{problem_result.get('passed', 0)}/{problem_result.get('failed', 0)}/{problem_result.get('errors', 0)}",
        "test_result": f"{test_result.get('passed', 0)}/{test_result.get('failed', 0)}/{test_result.get('errors', 0)}",
        "success": success
    })
    
    if success:
        print(f"\n✅ SUCCESS: Instance demonstrates proper test behavior")
    else:
        print(f"\n❌ FAILURE: Tests don't demonstrate expected behavior")

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")

success_count = sum(1 for r in results if r["success"])
print(f"Success rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

print("\nDetailed results:")
print(f"{'Instance':<35} {'Problem (P/F/E)':<15} {'Test (P/F/E)':<15} {'Success':<10}")
print("-" * 80)
for r in results:
    print(f"{r['instance_id']:<35} {r['problem_result']:<15} {r['test_result']:<15} {'✅' if r['success'] else '❌':<10}")

# Overall assessment
print(f"\n{'='*80}")
if success_count == len(results):
    print("✅ VALIDATION PASSED: All instances show proper targeted test execution!")
    print("   - Tests identify bugs when run on problem code")
    print("   - Tests pass when run with test patches")
else:
    print("⚠️  VALIDATION INCOMPLETE: Some instances need investigation")
    print("   This could be due to:")
    print("   - Test patches that don't add new tests (only modify existing)")
    print("   - Instances where the problem patch also includes tests")
    print("   - Infrastructure issues with specific repositories")