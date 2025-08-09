#!/usr/bin/env python3
"""
End-to-end test of the complete SWE-Bench evaluation system.
Tests the new worker_v2 with evaluator module.
"""

import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

import worker_v2
import evaluator

# Load a Django instance for testing
dataset_path = Path(__file__).parent / 'swe_bench_django.jsonl'
with open(dataset_path) as f:
    instance = json.loads(f.readline())

print(f"Testing end-to-end with instance: {instance['instance_id']}")
print(f"Repo: {instance['repo']}")

# Test 1: Direct evaluation with known good patch
print("\n" + "="*60)
print("Test 1: Direct evaluation with known good patch")
print("="*60)

# Create a temporary worktree for testing
import tempfile
import git_utils

cache_dir = Path("../../artifacts/cache").resolve()
work_dir = Path(tempfile.mkdtemp(prefix="swe_e2e_test_"))

try:
    repo_url = f"https://github.com/{instance['repo']}.git"
    base_commit = instance['base_commit']
    
    with git_utils.checkout_worktree(repo_url, base_commit, cache_dir, work_dir) as workdir:
        print(f"Created worktree at: {workdir}")
        
        # Test direct evaluation
        result = evaluator.evaluate_patch(
            instance,
            instance['patch'],
            str(workdir),
            force_local=True
        )
        
        print(f"\nDirect evaluation result:")
        print(f"  Passed: {result['passed']}")
        print(f"  Error: {result.get('error', 'None')}")
        print(f"  Test files: {result.get('test_files', [])}")
        
        direct_eval_passed = result['passed']
        
except Exception as e:
    print(f"Direct evaluation failed with exception: {e}")
    direct_eval_passed = False

# Test 2: Worker solving (simulated)
print("\n" + "="*60)
print("Test 2: Worker solving simulation")
print("="*60)

# Create a worker
worker = worker_v2.Worker(
    cache_dir=cache_dir,
    work_dir=work_dir,
    max_iterations=1,  # Just one iteration for testing
    timeout_per_iteration=300,
    with_mcp=False,  # No MCP for this test
    force_local=True  # Force local evaluation
)

# Since we can't actually call Claude, let's test the evaluation path directly
# by creating a mock Claude result
mock_claude_result = {
    'success': True,
    'response': f"""
I'll solve this Django issue.

<FINAL_DIFF>
{instance['patch']}
</FINAL_DIFF>
"""
}

# Test patch extraction
import patch_utils
extracted_patch = patch_utils.extract_diff_from_response(mock_claude_result['response'])
print(f"Patch extraction: {'✅ Success' if extracted_patch else '❌ Failed'}")

if extracted_patch:
    cleaned_patch = patch_utils.validate_and_clean_patch(extracted_patch, instance['instance_id'])
    print(f"Patch validation: {'✅ Success' if cleaned_patch else '❌ Failed'}")

# Test 3: Validate evaluation consistency
print("\n" + "="*60)
print("Test 3: Evaluation consistency check")
print("="*60)

# The evaluator should give consistent results
consistency_results = []

for i in range(3):
    with git_utils.checkout_worktree(repo_url, base_commit, cache_dir, work_dir) as workdir:
        result = evaluator.evaluate_patch(
            instance,
            instance['patch'],
            str(workdir),
            force_local=True
        )
        consistency_results.append(result['passed'])

all_consistent = all(r == consistency_results[0] for r in consistency_results)
print(f"Consistency check (3 runs): {'✅ All consistent' if all_consistent else '❌ Inconsistent'}")
print(f"Results: {consistency_results}")

# Summary
print("\n" + "="*60)
print("END-TO-END TEST SUMMARY")
print("="*60)

print(f"Direct evaluation: {'✅ Passed' if direct_eval_passed else '❌ Failed'}")
print(f"Patch extraction: {'✅ Works' if extracted_patch else '❌ Failed'}")
print(f"Evaluation consistency: {'✅ Consistent' if all_consistent else '❌ Inconsistent'}")

overall_success = direct_eval_passed and extracted_patch and all_consistent
print(f"\nOverall: {'✅ SUCCESS - System is ready!' if overall_success else '❌ FAILED - Issues found'}")

# Cleanup
if work_dir.exists():
    import shutil
    shutil.rmtree(work_dir)

print("\nEnd-to-end test complete!")