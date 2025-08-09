#!/usr/bin/env python3
"""
Validate the evaluation function with known good/bad patches.
This ensures f(patch) => pass/fail works correctly.
"""

import json
import logging
import sys
from pathlib import Path

try:
    from . import git_utils
    from . import evaluator
    from .fetch_data import load_instances
except ImportError:
    import git_utils
    import evaluator
    from fetch_data import load_instances

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def validate_instance(instance):
    """Validate evaluation for a single instance."""
    
    instance_id = instance['instance_id']
    repo_url = f"https://github.com/{instance['repo']}.git"
    base_commit = instance['base_commit']
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Validating {instance_id}")
    logger.info(f"Repo: {instance['repo']} @ {base_commit}")
    
    # Skip complex repos for now
    if evaluator.should_use_docker(instance):
        logger.warning(f"Skipping {instance_id} - requires Docker")
        return None
    
    results = {
        "instance_id": instance_id,
        "known_good": False,
        "empty_patch": False,
        "overall": False
    }
    
    try:
        # Create a working directory
        cache_dir = Path("runner/artifacts/cache")
        work_dir = Path("runner/artifacts/validation_worktrees")
        work_dir.mkdir(parents=True, exist_ok=True)
        
        with git_utils.checkout_worktree(repo_url, base_commit, cache_dir, work_dir) as workdir:
            logger.info(f"Checked out to: {workdir}")
            
            # First, check if pip install works
            venv_path = Path(workdir) / '.venv'
            import subprocess
            
            # Create venv
            subprocess.run(
                [sys.executable, '-m', 'venv', str(venv_path)],
                check=True
            )
            
            # Try to install the package
            pip_cmd = str(venv_path / 'bin' / 'pip')
            logger.info("Installing dependencies...")
            
            install_result = subprocess.run(
                [pip_cmd, 'install', '-e', '.'],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if install_result.returncode != 0:
                logger.error(f"Pip install failed: {install_result.stderr}")
                results["error"] = "pip_install_failed"
                return results
            
            # Test 1: Known good patch should pass
            logger.info("\nTest 1: Applying known good patch...")
            good_result = evaluator.evaluate_patch(
                instance, 
                instance['patch'],
                str(workdir),
                force_local=True
            )
            
            results["known_good"] = good_result["passed"]
            results["known_good_details"] = good_result
            
            if good_result["passed"]:
                logger.info("✅ Known good patch PASSED (correct)")
            else:
                logger.error(f"❌ Known good patch FAILED (incorrect): {good_result['error']}")
                if good_result.get('test_output'):
                    logger.error(f"Test output:\n{good_result['test_output'][-500:]}")
            
            # Reset the repo
            subprocess.run(['git', 'reset', '--hard'], cwd=workdir)
            subprocess.run(['git', 'clean', '-xfd'], cwd=workdir)
            
            # Test 2: Empty patch should fail
            logger.info("\nTest 2: Applying empty patch...")
            empty_result = evaluator.evaluate_patch(
                instance,
                "",  # Empty patch
                str(workdir),
                force_local=True
            )
            
            # For empty patch, we expect it to fail
            results["empty_patch"] = not empty_result["passed"]
            results["empty_patch_details"] = empty_result
            
            if not empty_result["passed"]:
                logger.info("✅ Empty patch FAILED (correct)")
            else:
                logger.error("❌ Empty patch PASSED (incorrect)")
            
            # Overall success: both tests behaved correctly
            results["overall"] = results["known_good"] and results["empty_patch"]
            
    except Exception as e:
        logger.error(f"Exception during validation: {e}")
        results["error"] = str(e)
    
    return results


def main():
    """Validate evaluator with a sample of instances."""
    
    # Load instances - try Django first for simpler testing
    try:
        instances = load_instances("swe_bench_django.jsonl")
    except:
        instances = load_instances()
    
    # Start with Django instances - they're simpler
    django_instances = [i for i in instances if 'django' in i['repo'].lower()]
    
    if not django_instances:
        # Try Flask or requests
        simple_repos = ['pallets/flask', 'psf/requests', 'django/django']
        simple_instances = [i for i in instances if i['repo'] in simple_repos]
        instances_to_test = simple_instances[:3] if simple_instances else instances[:3]
    else:
        instances_to_test = django_instances[:3]
    
    logger.info(f"Testing {len(instances_to_test)} instances")
    
    results = []
    for instance in instances_to_test:
        result = validate_instance(instance)
        if result:
            results.append(result)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("VALIDATION SUMMARY")
    logger.info(f"{'='*60}")
    
    total = len(results)
    successful = sum(1 for r in results if r.get('overall', False))
    
    for result in results:
        status = "✅" if result.get('overall') else "❌"
        logger.info(f"{status} {result['instance_id']}")
        if not result.get('overall'):
            if not result.get('known_good'):
                logger.info(f"  - Known patch failed")
            if not result.get('empty_patch'):
                logger.info(f"  - Empty patch didn't fail") 
            if result.get('error'):
                logger.info(f"  - Error: {result['error']}")
    
    logger.info(f"\nOverall: {successful}/{total} instances validated successfully")
    
    # Save detailed results
    output_file = Path("runner/artifacts/validation_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nDetailed results saved to: {output_file}")
    
    return successful == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)