#!/usr/bin/env python3
"""
Analyze test_patch patterns across multiple instances to understand
how SWE-Bench specifies which tests to run.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# Load all Django instances
django_file = Path("/Users/luka/src/cc/mcp-the-force-swebench/runner/src/swe_bench_django.jsonl")
instances = []
with open(django_file) as f:
    for line in f:
        instances.append(json.loads(line))

print(f"Analyzing {len(instances)} Django instances\n")

# Analyze test_patch patterns
file_types = defaultdict(int)
test_patterns = defaultdict(list)

for instance in instances:
    instance_id = instance['instance_id']
    test_patch = instance.get('test_patch', '')
    
    # Extract files from test_patch
    files = []
    for line in test_patch.split('\n'):
        if line.startswith('diff --git a/'):
            match = re.match(r'diff --git a/(.*?) b/', line)
            if match:
                file_path = match.group(1)
                files.append(file_path)
                
                # Categorize by file type
                if file_path.endswith('.py'):
                    file_types['Python'] += 1
                elif file_path.endswith('.txt'):
                    file_types['Text'] += 1
                else:
                    file_types['Other'] += 1
                
                # Track patterns
                if 'test' in file_path.lower():
                    test_patterns['has_test_in_path'].append((instance_id, file_path))
                if file_path.startswith('tests/'):
                    test_patterns['in_tests_dir'].append((instance_id, file_path))
    
    # Print instance summary
    print(f"{instance_id}:")
    print(f"  Files modified in test_patch: {files}")
    if not files:
        print(f"  WARNING: No files found in test_patch!")
    print()

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"\nFile types in test_patch:")
for ftype, count in sorted(file_types.items()):
    print(f"  {ftype}: {count}")

print(f"\nTest patterns:")
for pattern, examples in test_patterns.items():
    print(f"  {pattern}: {len(examples)} instances")
    if examples:
        print(f"    Example: {examples[0]}")

# Look for a pattern of how to map test_patch files to actual test commands
print("\n" + "="*60)
print("HYPOTHESIS: How to find which tests to run")
print("="*60)
print("""
Based on the analysis:
1. If test_patch modifies .py files in tests/, run those specific test files
2. If test_patch modifies .txt or data files, find Python tests that use those files
3. For Django specifically, look for test files in the same directory as the data files
""")