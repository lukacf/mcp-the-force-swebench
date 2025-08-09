#!/usr/bin/env python3
"""Systematically test all repositories in SWE-Bench to ensure evaluator compatibility."""

import json
import time
from evaluator import evaluate_patch, extract_test_files_from_patch

# All unique repos in SWE-Bench
REPOS = [
    "django/django",
    "sympy/sympy", 
    "sphinx-doc/sphinx",
    "matplotlib/matplotlib",
    "scikit-learn/scikit-learn",
    "pydata/xarray",
    "astropy/astropy",
    "pytest-dev/pytest",
    "pylint-dev/pylint",
    "psf/requests",
    "mwaskom/seaborn",
    "pallets/flask"
]

def get_instance_for_repo(repo):
    """Get the first instance for a given repo."""
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instance = json.loads(line)
            if instance['repo'] == repo:
                return instance
    return None

def test_repo(repo):
    """Test a single repository and return results."""
    print(f"\n{'='*60}")
    print(f"Testing: {repo}")
    print(f"{'='*60}")
    
    instance = get_instance_for_repo(repo)
    if not instance:
        return {
            'repo': repo,
            'status': 'ERROR',
            'error': 'No instance found',
            'time': 0
        }
    
    print(f"Instance: {instance['instance_id']}")
    
    # Extract test files
    test_files = extract_test_files_from_patch(instance['test_patch'])
    print(f"Test files: {test_files}")
    
    # Test with correct patch
    start_time = time.time()
    try:
        result = evaluate_patch(instance, instance['patch'])
        elapsed = time.time() - start_time
        
        print(f"Result: {'PASSED' if result['passed'] else 'FAILED'}")
        if result.get('stats'):
            print(f"Stats: {result['stats']}")
        if result.get('error'):
            print(f"Error: {result['error']}")
            
        # Check for specific issues
        issues = []
        if result.get('test_output'):
            output = result['test_output']
            if 'ModuleNotFoundError' in output:
                issues.append('Missing dependencies')
            if 'command not found' in output:
                issues.append('Missing test runner')
            if 'No such file or directory' in output:
                issues.append('Path issues')
                
        return {
            'repo': repo,
            'instance_id': instance['instance_id'],
            'status': 'PASSED' if result['passed'] else 'FAILED',
            'error': result.get('error', ''),
            'time': elapsed,
            'test_files': test_files,
            'issues': issues,
            'stats': result.get('stats', {})
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Exception: {str(e)}")
        return {
            'repo': repo,
            'instance_id': instance['instance_id'],
            'status': 'EXCEPTION',
            'error': str(e),
            'time': elapsed
        }

def main():
    """Run systematic tests on all repositories."""
    print("SYSTEMATIC REPOSITORY TESTING")
    print("="*60)
    print(f"Testing {len(REPOS)} unique repositories from SWE-Bench")
    
    results = []
    total_start = time.time()
    
    for repo in REPOS:
        result = test_repo(repo)
        results.append(result)
        time.sleep(1)  # Be nice to the GCP server
    
    total_time = time.time() - total_start
    
    # Summary report
    print(f"\n{'='*60}")
    print("SUMMARY REPORT")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    errors = sum(1 for r in results if r['status'] in ['ERROR', 'EXCEPTION'])
    
    print(f"\nTotal repositories tested: {len(REPOS)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Total time: {total_time:.1f}s")
    
    print("\nDetailed Results:")
    print(f"{'Repository':<30} {'Status':<10} {'Time':<8} {'Issues'}")
    print("-"*70)
    
    for r in results:
        issues = ', '.join(r.get('issues', [])) if r.get('issues') else ''
        print(f"{r['repo']:<30} {r['status']:<10} {r['time']:>6.1f}s  {issues}")
    
    # Show any failed/error cases in detail
    if failed + errors > 0:
        print(f"\n{'='*60}")
        print("FAILED/ERROR DETAILS")
        print(f"{'='*60}")
        
        for r in results:
            if r['status'] in ['FAILED', 'ERROR', 'EXCEPTION']:
                print(f"\n{r['repo']} ({r.get('instance_id', 'N/A')}):")
                print(f"  Status: {r['status']}")
                print(f"  Error: {r.get('error', 'Unknown')}")
                if r.get('issues'):
                    print(f"  Issues: {', '.join(r['issues'])}")

if __name__ == "__main__":
    main()