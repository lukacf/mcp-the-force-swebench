#!/usr/bin/env python3
"""
Test Docker evaluation with an Astropy instance.
Astropy is one of the complex repos that needs Docker.
"""

import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

import evaluator

# Load an Astropy instance
dataset_path = Path(__file__).parent.parent / 'swe_bench_instances.jsonl'
astropy_instance = None

with open(dataset_path) as f:
    for line in f:
        instance = json.loads(line)
        if instance['repo'] == 'astropy/astropy':
            astropy_instance = instance
            break

if not astropy_instance:
    print("No Astropy instance found!")
    sys.exit(1)

print(f"Testing instance: {astropy_instance['instance_id']}")
print(f"Repo: {astropy_instance['repo']}")

# Test 1: Evaluate with known good patch (should pass)
print("\n" + "="*60)
print("Testing with KNOWN GOOD patch via Docker")
print("="*60)

result = evaluator.evaluate_patch(
    astropy_instance, 
    astropy_instance['patch'],
    force_local=False  # Allow Docker
)

print(f"\nResult:")
print(f"  Method: {result.get('method', 'unknown')}")
print(f"  Passed: {result['passed']}")
print(f"  Error: {result.get('error', 'None')}")
print(f"  Test files: {result.get('test_files', [])}")

if result.get('test_output'):
    print(f"\nTest output (last 500 chars):")
    print(result['test_output'][-500:])

# Test 2: Evaluate with empty patch (should fail)
print("\n" + "="*60)
print("Testing with EMPTY patch via Docker")
print("="*60)

result2 = evaluator.evaluate_patch(
    astropy_instance,
    "",
    force_local=False
)

print(f"\nResult:")
print(f"  Method: {result2.get('method', 'unknown')}")
print(f"  Passed: {result2['passed']}")
print(f"  Error: {result2.get('error', 'None')}")

# Summary
print("\n" + "="*60)
print("DOCKER VALIDATION SUMMARY")
print("="*60)

good_patch_correct = result['passed'] == True
empty_patch_correct = result2['passed'] == False

print(f"Known good patch passed: {'✅' if good_patch_correct else '❌'}")
print(f"Empty patch failed: {'✅' if empty_patch_correct else '❌'}")
print(f"Overall: {'✅ SUCCESS' if (good_patch_correct and empty_patch_correct) else '❌ FAILED'}")

print("\nDocker evaluation test complete!")