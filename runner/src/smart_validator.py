#!/usr/bin/env python3
"""Smart validation that understands different test_patch patterns."""

import json
import re
from evaluator import evaluate_patch

def extract_smart_test_targets(test_patch):
    """Extract specific test targets based on test_patch content."""
    
    # Look for new test functions
    new_test_functions = re.findall(r'^\+def (test_\w+)', test_patch, re.MULTILINE)
    if new_test_functions:
        return {
            'type': 'new_functions',
            'targets': new_test_functions,
            'description': f"New test functions: {', '.join(new_test_functions)}"
        }
    
    # Look for modified test files
    test_files = []
    for match in re.finditer(r'^diff --git a/(.*?\.py) b/', test_patch, re.MULTILINE):
        file_path = match.group(1)
        if 'test' in file_path:
            test_files.append(file_path)
    
    if test_files:
        return {
            'type': 'test_files',
            'targets': test_files,
            'description': f"Test files: {', '.join(test_files)}"
        }
    
    # Data files only - need to find tests that use them
    data_files = []
    for match in re.finditer(r'^diff --git a/(.*?) b/', test_patch, re.MULTILINE):
        file_path = match.group(1)
        if not file_path.endswith('.py'):
            data_files.append(file_path)
    
    if data_files:
        # Extract directory
        dirs = list(set(str(f).rsplit('/', 1)[0] for f in data_files))
        return {
            'type': 'data_files',
            'targets': dirs,
            'description': f"Data files in: {', '.join(dirs)} (may run too many tests)"
        }
    
    return {
        'type': 'unknown',
        'targets': [],
        'description': "Could not determine test targets"
    }


def validate_smart(instance, show_output=False):
    """Validate instance with smart test targeting."""
    
    instance_id = instance['instance_id']
    repo = instance['repo']
    
    # Extract smart test targets
    test_info = extract_smart_test_targets(instance['test_patch'])
    
    print(f"\n{'='*60}")
    print(f"{instance_id}")
    print(f"Repository: {repo}")
    print(f"Test approach: {test_info['description']}")
    
    # For new test functions in pytest repos, we need special handling
    if test_info['type'] == 'new_functions' and 'pytest' not in instance_id:
        # Construct a special patch that includes both code changes and new tests
        combined_patch = instance['patch'] + '\n' + instance['test_patch']
        
        # The new tests should fail without the code fix
        print("\n1. Testing new tests WITHOUT fix (should fail):")
        
        # Create a patch with just the test additions
        test_only_patch = instance['test_patch']
        
        result = evaluate_patch(instance, test_only_patch)
        print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"   Stats: {result.get('stats', {})}")
        
        without_fix_passed = result['passed']
        
        # Now test with the fix
        print("\n2. Testing WITH fix (should pass):")
        result = evaluate_patch(instance, combined_patch)
        print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"   Stats: {result.get('stats', {})}")
        
        with_fix_passed = result['passed']
        
    else:
        # Standard approach
        print("\n1. Testing WITHOUT fix:")
        result = evaluate_patch(instance, "")
        print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"   Stats: {result.get('stats', {})}")
        without_fix_passed = result['passed']
        
        print("\n2. Testing WITH fix:")
        combined_patch = instance['patch'] + '\n' + instance['test_patch']
        result = evaluate_patch(instance, combined_patch)
        print(f"   Result: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"   Stats: {result.get('stats', {})}")
        with_fix_passed = result['passed']
    
    # Validation
    print("\nValidation:")
    if not without_fix_passed and with_fix_passed:
        print("✅ CORRECT: Bug present → fixed")
        return True
    elif without_fix_passed and with_fix_passed:
        print("⚠️  WARNING: Tests pass even without fix")
        if test_info['type'] == 'data_files':
            print("   This is expected when running all tests in a directory")
            print("   Only specific tests that use the data files would fail")
        return None  # Uncertain
    else:
        print("❌ FAILED: Unexpected behavior")
        return False


# Test some instances
print("SMART VALIDATION TEST")
print("="*60)

test_instances = [
    "pallets__flask-5014",     # Has new test function
    "sympy__sympy-13895",      # Has new test function  
    "django__django-10097",    # Only data files
]

for instance_id in test_instances:
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            inst = json.loads(line)
            if inst['instance_id'] == instance_id:
                validate_smart(inst)
                break