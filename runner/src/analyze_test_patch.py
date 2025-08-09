#!/usr/bin/env python3
"""Analyze test_patch to understand what tests actually verify the bug fix."""

import json
import re

def analyze_test_patch(instance_id):
    """Analyze what a test_patch actually tests."""
    
    # Load instance
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            inst = json.loads(line)
            if inst['instance_id'] == instance_id:
                break
    
    print(f"\nAnalyzing {instance_id}")
    print("="*60)
    
    # Parse test_patch
    test_patch = inst['test_patch']
    modified_files = []
    
    # Extract modified files
    for match in re.finditer(r'^diff --git a/(.*?) b/(.*?)$', test_patch, re.MULTILINE):
        file_path = match.group(1)
        modified_files.append(file_path)
    
    print(f"Test patch modifies {len(modified_files)} files:")
    for f in modified_files:
        print(f"  - {f}")
    
    # Check if test patch adds new test functions
    new_test_functions = re.findall(r'^\+def (test_\w+)', test_patch, re.MULTILINE)
    if new_test_functions:
        print(f"\nAdds {len(new_test_functions)} new test functions:")
        for func in new_test_functions:
            print(f"  - {func}")
    
    # Check if it modifies existing tests
    modified_tests = re.findall(r'^@@ .* def (test_\w+)', test_patch, re.MULTILINE)
    if modified_tests:
        print(f"\nModifies {len(modified_tests)} existing test functions:")
        for func in modified_tests:
            print(f"  - {func}")
    
    # Check for data file modifications
    data_files = [f for f in modified_files if not f.endswith('.py')]
    if data_files:
        print(f"\nModifies {len(data_files)} data files:")
        for f in data_files:
            print(f"  - {f}")
            
        # Show what's added to data files
        print("\nData additions:")
        current_file = None
        for line in test_patch.split('\n'):
            if line.startswith('diff --git'):
                match = re.search(r'a/(.*?) b/', line)
                if match:
                    current_file = match.group(1)
            elif line.startswith('+') and not line.startswith('+++'):
                if current_file and current_file in data_files:
                    print(f"  {current_file}: {line[1:]}")
    
    # Determine test strategy
    print("\nTest Strategy:")
    if new_test_functions:
        print("  - Run only the new test functions")
    elif data_files and not any(f.endswith('.py') for f in modified_files):
        print("  - Tests use modified data files")
        print("  - Need to run tests that load these data files")
        print("  - Problem: We're running ALL tests in the directory!")
    
    return modified_files


# Analyze several instances
instances = [
    "django__django-10097",
    "pallets__flask-5014", 
    "astropy__astropy-12907",
    "sympy__sympy-13895"
]

print("TEST PATCH ANALYSIS")
print("="*60)

for instance_id in instances:
    analyze_test_patch(instance_id)