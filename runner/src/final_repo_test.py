#!/usr/bin/env python3
"""Final test of all repositories after pytest auto-install fix."""

import json
from evaluator import evaluate_patch, extract_test_files_from_patch

# Test these repos that previously failed
PREVIOUSLY_FAILED = [
    ("sympy/sympy", "sympy__sympy-11618"),
    ("sphinx-doc/sphinx", "sphinx-doc__sphinx-3234"),
    ("matplotlib/matplotlib", "matplotlib__matplotlib-13448"),
    ("pylint-dev/pylint", "pylint-dev__pylint-3604"),
    ("mwaskom/seaborn", "mwaskom__seaborn-2229")
]

print("TESTING PREVIOUSLY FAILED REPOS WITH PYTEST AUTO-INSTALL FIX")
print("="*60)

results = []

for repo, instance_id in PREVIOUSLY_FAILED:
    print(f"\nTesting {repo}...")
    
    # Get the instance
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instance = json.loads(line)
            if instance['instance_id'] == instance_id:
                break
    
    # Test with correct patch
    result = evaluate_patch(instance, instance['patch'])
    
    status = "✅ PASSED" if result['passed'] else "❌ FAILED"
    print(f"  Result: {status}")
    print(f"  Time: {result.get('stats', {}).get('duration', '?')}s")
    
    results.append({
        'repo': repo,
        'passed': result['passed'],
        'duration': result.get('stats', {}).get('duration', 0)
    })

print("\n" + "="*60)
print("SUMMARY")
print("="*60)

passed = sum(1 for r in results if r['passed'])
total_time = sum(r['duration'] for r in results)

print(f"\nTotal tested: {len(results)}")
print(f"Passed: {passed}/{len(results)}")
print(f"Total time: {total_time:.1f}s")
print(f"Average time: {total_time/len(results):.1f}s per repo")

if passed == len(results):
    print("\n🎉 ALL PREVIOUSLY FAILING REPOS NOW PASS!")
    print("The pytest auto-install fix resolved all issues.")
else:
    print(f"\n⚠️  {len(results) - passed} repos still have issues")