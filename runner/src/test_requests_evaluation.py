#!/usr/bin/env python3
"""
Test evaluation with psf/requests instances.
Requests is a simpler repo without complex dependencies.
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

# Load requests instances from dataset
requests_instances = []
dataset_path = Path(__file__).parent.parent / 'swe_bench_instances.jsonl'
with open(dataset_path) as f:
    for line in f:
        instance = json.loads(line)
        if instance['repo'] == 'psf/requests':
            requests_instances.append(instance)

print(f"Found {len(requests_instances)} requests instances")

if not requests_instances:
    print("No requests instances found!")
    sys.exit(1)

# Test first requests instance
instance = requests_instances[0]

print(f"\nTesting instance: {instance['instance_id']}")
print(f"Repo: {instance['repo']}")
print(f"Problem statement preview: {instance['problem_statement'][:200]}...")

# Create a temp worktree
repo_url = f"https://github.com/{instance['repo']}.git"
base_commit = instance['base_commit']

cache_dir = Path("../../artifacts/cache").resolve()
work_dir = Path(tempfile.mkdtemp(prefix="swe_requests_test_"))

print(f"\nCache dir: {cache_dir}")
print(f"Work dir: {work_dir}")

try:
    with git_utils.checkout_worktree(repo_url, base_commit, cache_dir, work_dir) as workdir:
        print(f"Checked out to: {workdir}")
        
        # Install dependencies
        print("\nInstalling requests dependencies...")
        
        # Check for setup.py
        if (Path(workdir) / 'setup.py').exists():
            # Install in editable mode
            subprocess.run(
                ['pip', 'install', '-e', '.'],
                cwd=workdir,
                capture_output=True
            )
        
        # Install test dependencies
        test_requirements = [
            'requirements-dev.txt',
            'dev-requirements.txt',
            'test-requirements.txt'
        ]
        
        for req_file in test_requirements:
            req_path = Path(workdir) / req_file
            if req_path.exists():
                print(f"Installing from {req_file}")
                subprocess.run(
                    ['pip', 'install', '-r', req_file],
                    cwd=workdir,
                    capture_output=True
                )
        
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
        
        # Test 4: Wrong patch (should fail)
        print("\n" + "="*60)
        print("Testing with WRONG patch (should fail)")
        print("="*60)
        
        # Create a nonsense patch
        wrong_patch = """diff --git a/requests/models.py b/requests/models.py
--- a/requests/models.py
+++ b/requests/models.py
@@ -1,5 +1,5 @@
 import os
-import sys
+import sys  # This is a nonsense change
 
 # Rest of file...
"""
        
        result3 = evaluator.evaluate_patch_locally(instance, wrong_patch, str(workdir))
        
        print(f"\nResult:")
        print(f"  Passed: {result3['passed']}")
        print(f"  Error: {result3.get('error', 'None')}")
        
        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        good_patch_correct = result['passed'] == True
        empty_patch_correct = result2['passed'] == False
        wrong_patch_correct = result3['passed'] == False
        
        print(f"Known good patch passed: {'✅' if good_patch_correct else '❌'}")
        print(f"Empty patch failed: {'✅' if empty_patch_correct else '❌'}")
        print(f"Wrong patch failed: {'✅' if wrong_patch_correct else '❌'}")
        print(f"Overall: {'✅ SUCCESS' if (good_patch_correct and empty_patch_correct and wrong_patch_correct) else '❌ FAILED'}")
        
except Exception as e:
    print(f"\nException: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if work_dir.exists():
        import shutil
        shutil.rmtree(work_dir)

print("\nTest complete!")