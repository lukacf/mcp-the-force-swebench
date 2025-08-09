#!/usr/bin/env python3
"""
Test evaluation with a Django instance directly.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

import evaluator
import git_utils

# Load Django instance
with open('swe_bench_django.jsonl') as f:
    instance = json.loads(f.readline())

print(f"Testing instance: {instance['instance_id']}")
print(f"Repo: {instance['repo']}")

# Create a temp worktree
repo_url = f"https://github.com/{instance['repo']}.git"
base_commit = instance['base_commit']

cache_dir = Path("../../artifacts/cache").resolve()
work_dir = Path(tempfile.mkdtemp(prefix="swe_test_"))

print(f"\nCache dir: {cache_dir}")
print(f"Work dir: {work_dir}")

try:
    with git_utils.checkout_worktree(repo_url, base_commit, cache_dir, work_dir) as workdir:
        print(f"Checked out to: {workdir}")
        
        # Test 1: Extract test files from test_patch
        test_patch = instance['test_patch']
        test_files = evaluator.extract_test_files_from_patch(test_patch, str(workdir))
        print(f"\nExtracted test files/dirs: {test_files}")
        
        # Test 2: Apply the known good patch and test_patch
        print("\n" + "="*60)
        print("Testing with KNOWN GOOD patch (should pass)")
        print("="*60)
        
        result = evaluator.evaluate_patch_locally(instance, instance['patch'], str(workdir))
        
        print(f"\nResult:")
        print(f"  Passed: {result['passed']}")
        print(f"  Error: {result.get('error', 'None')}")
        print(f"  Test files: {result.get('test_files', [])}")
        
        if result.get('test_output'):
            print(f"\nTest output (last 1000 chars):")
            print(result['test_output'][-1000:])
        
        # Reset
        subprocess.run(['git', 'reset', '--hard'], cwd=workdir)
        subprocess.run(['git', 'clean', '-xfd'], cwd=workdir)
        
        # Test 3: Empty patch (should fail)
        print("\n" + "="*60)
        print("Testing with EMPTY patch (should fail)")
        print("="*60)
        
        result2 = evaluator.evaluate_patch_locally(instance, "", str(workdir))
        
        print(f"\nResult:")
        print(f"  Passed: {result2['passed']}")
        print(f"  Error: {result2.get('error', 'None')}")
        
        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        good_patch_correct = result['passed'] == True
        empty_patch_correct = result2['passed'] == False
        
        print(f"Known good patch passed: {'✅' if good_patch_correct else '❌'}")
        print(f"Empty patch failed: {'✅' if empty_patch_correct else '❌'}")
        print(f"Overall: {'✅ SUCCESS' if (good_patch_correct and empty_patch_correct) else '❌ FAILED'}")
        
except Exception as e:
    print(f"\nException: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if work_dir.exists():
        import shutil
        shutil.rmtree(work_dir)