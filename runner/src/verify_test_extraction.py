#!/usr/bin/env python3
"""Verify that we're extracting and running the correct tests."""

import json
from evaluator import extract_test_files_from_patch

# Load a specific instance
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] == 'sympy__sympy-11618':
            instances.append(inst)
            break

if not instances:
    print("Instance not found!")
    exit(1)

instance = instances[0]
print(f"Instance: {instance['instance_id']}")
print(f"\nTest patch preview (first 1000 chars):")
print(instance['test_patch'][:1000])
print("\n" + "="*80)

# Extract test files
test_files = extract_test_files_from_patch(instance['test_patch'])
print(f"\nExtracted test files: {test_files}")

# Check if test patch modifies existing tests or adds new ones
test_patch_lines = instance['test_patch'].split('\n')
for i, line in enumerate(test_patch_lines[:50]):
    if line.startswith('@@'):
        print(f"\nHunk at line {i}: {line}")
        # Show context
        for j in range(i+1, min(i+10, len(test_patch_lines))):
            if test_patch_lines[j].startswith('@@') or test_patch_lines[j].startswith('diff'):
                break
            print(f"  {test_patch_lines[j]}")

# Let's also check the specific test content
print("\n" + "="*80)
print("Test patch adds these test lines:")
for line in test_patch_lines:
    if line.startswith('+') and 'def test' in line:
        print(f"  {line}")
    elif line.startswith('+') and 'assert' in line:
        print(f"  {line}")