#!/usr/bin/env python3
"""Quick test of a few key repositories."""

import json
from evaluator import evaluate_patch, extract_test_files_from_patch

# Test these key repos representing different frameworks
TEST_REPOS = [
    "django/django",      # Django - custom test runner
    "sympy/sympy",        # Scientific computing
    "pytest-dev/pytest",  # Testing framework itself
    "psf/requests",       # Simple library
    "pallets/flask",      # Web framework
    "scikit-learn/scikit-learn"  # ML library
]

def test_repo(repo):
    """Test a single repo."""
    print(f"\n{'='*50}")
    print(f"Testing: {repo}")
    print(f"{'='*50}")
    
    # Get first instance
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instance = json.loads(line)
            if instance['repo'] == repo:
                break
        else:
            print(f"ERROR: No instance found for {repo}")
            return
    
    print(f"Instance: {instance['instance_id']}")
    test_files = extract_test_files_from_patch(instance['test_patch'])
    print(f"Test files: {test_files[:3]}...")  # Show first 3
    
    # Test with correct patch
    result = evaluate_patch(instance, instance['patch'])
    
    print(f"Result: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
    if result.get('error'):
        print(f"Error: {result['error'][:100]}...")
    if result.get('stats'):
        print(f"Stats: {result['stats']}")
    
    # Check for common issues
    if result.get('test_output'):
        output = result['test_output']
        if 'ModuleNotFoundError' in output:
            print("⚠️  Missing module dependency")
        if 'No such file or directory' in output:
            print("⚠️  Path/file issue")
        if 'command not found' in output:
            print("⚠️  Missing command")

# Test each repo
for repo in TEST_REPOS:
    test_repo(repo)