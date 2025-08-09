#!/usr/bin/env python3
"""Test Astropy instance to verify complex scientific packages work."""

import json
from evaluator import evaluate_patch

# Load Astropy instance
with open('astropy_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']}")
print(f"Repo: {instance['repo']}")
print(f"Problem: {instance['problem_statement'][:150]}...")

# Extract test files from test_patch
from evaluator import extract_test_files_from_patch
test_files = extract_test_files_from_patch(instance['test_patch'])
print(f"\nTest files that will be run: {test_files}")

# Test with the correct patch
print("\n" + "="*60)
print("Testing with CORRECT patch from SWE-Bench...")
print("="*60)

result = evaluate_patch(instance, instance['patch'])

print(f"\nResult: Passed={result['passed']}")
print(f"Test files run: {result.get('test_files', [])}")
if 'stats' in result:
    print(f"Stats: {result['stats']}")
if result.get('error'):
    print(f"Error: {result['error']}")

# Show a bit of the output
if result.get('test_output'):
    print("\nTest output (last 10 lines):")
    lines = result['test_output'].strip().split('\n')
    for line in lines[-10:]:
        print(f"  {line}")

print("\n" + "="*60)
print("Summary:")
print(f"- Docker container: ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance['instance_id']}:latest")
print(f"- Test framework: pytest (Astropy uses pytest)")
print(f"- Evaluation: {'PASSED' if result['passed'] else 'FAILED'}")