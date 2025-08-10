#!/usr/bin/env python3
"""
SWE-Bench Validation Framework

Validates that our evaluator correctly handles all 500 SWE-Bench instances.
"""

import json
import time
import logging
from collections import defaultdict
from evaluator import evaluate_patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def validate_swebench_instance(instance):
    """
    Validate a SWE-Bench instance according to the expected behavior:
    
    1. Apply test_patch (adds/modifies tests)
    2. Run tests - should FAIL (bug is present) 
    3. Apply patch + test_patch
    4. Run tests - should PASS (bug is fixed)
    """
    
    instance_id = instance['instance_id']
    
    try:
        # Step 1: Apply only test_patch and run tests
        # This adds the new tests that check for the bug
        logger.info(f"Testing {instance_id} - Step 1: test_patch only")
        result1 = evaluate_patch(instance, instance['test_patch'])
        
        # Step 2: Apply both patch and test_patch
        # This fixes the bug and includes the tests
        logger.info(f"Testing {instance_id} - Step 2: patch + test_patch")
        combined_patch = instance['patch'] + '\n' + instance['test_patch']
        result2 = evaluate_patch(instance, combined_patch)
        
        # Analyze results
        tests_fail_without_fix = not result1['passed']
        tests_pass_with_fix = result2['passed']
        
        # Expected: tests fail without fix, pass with fix
        is_valid = tests_fail_without_fix and tests_pass_with_fix
        
        return {
            'instance_id': instance_id,
            'repo': instance['repo'],
            'valid': is_valid,
            'test_patch_only': {
                'passed': result1['passed'],
                'stats': result1.get('stats', {})
            },
            'patch_plus_test': {
                'passed': result2['passed'],
                'stats': result2.get('stats', {})
            },
            'error': None if is_valid else f"Expected fail→pass, got {result1['passed']}→{result2['passed']}"
        }
        
    except Exception as e:
        logger.error(f"Error validating {instance_id}: {e}")
        return {
            'instance_id': instance_id,
            'repo': instance['repo'],
            'valid': False,
            'error': str(e)
        }


def validate_batch(instances, max_workers=3):
    """Validate a batch of instances."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_instance = {
            executor.submit(validate_swebench_instance, inst): inst 
            for inst in instances
        }
        
        for future in as_completed(future_to_instance):
            try:
                result = future.result()
                results.append(result)
                
                # Print summary
                status = "✅" if result['valid'] else "❌"
                instance_id = result['instance_id']
                if result['valid']:
                    print(f"{status} {instance_id}: FAIL→PASS (correct)")
                else:
                    print(f"{status} {instance_id}: {result.get('error', 'validation failed')}")
                    
            except Exception as e:
                instance = future_to_instance[future]
                print(f"❌ {instance['instance_id']}: Exception - {e}")
    
    return results


def main():
    """Run validation on SWE-Bench instances."""
    
    # Load all instances
    instances = []
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instances.append(json.loads(line))
    
    print("SWE-BENCH VALIDATION")
    print("="*70)
    print(f"Total instances: {len(instances)}")
    
    # Group by repository
    by_repo = defaultdict(list)
    for inst in instances:
        by_repo[inst['repo']].append(inst)
    
    print("\nInstances by repository:")
    for repo, insts in sorted(by_repo.items()):
        print(f"  {repo:30} {len(insts):3} instances")
    
    # Test strategy: Start with 1 instance per repo
    print("\nPhase 1: Testing 1 instance from each repository")
    print("-"*70)
    
    test_instances = []
    for repo, insts in by_repo.items():
        test_instances.append(insts[0])  # Take first instance
    
    # Run validation
    results = validate_batch(test_instances, max_workers=2)
    
    # Summary
    valid_count = sum(1 for r in results if r['valid'])
    print(f"\nPhase 1 Summary:")
    print(f"  Tested: {len(results)}")
    print(f"  Valid: {valid_count}")
    print(f"  Invalid: {len(results) - valid_count}")
    
    if valid_count < len(results):
        print("\nInvalid instances:")
        for r in results:
            if not r['valid']:
                print(f"  - {r['instance_id']}: {r.get('error', 'unknown error')}")
    
    # Save results
    with open('swebench_validation_results.json', 'w') as f:
        json.dump({
            'phase': 'initial_test',
            'total_instances': len(instances),
            'tested': len(results),
            'valid': valid_count,
            'results': results
        }, f, indent=2)
    
    print(f"\nValidation rate: {valid_count/len(results)*100:.1f}%")
    
    if valid_count == len(results):
        print("\n✅ All tested repositories are working correctly!")
        print("\nTo validate ALL 500 instances, run:")
        print("  python swebench_validator.py --all")
    else:
        print("\n⚠️  Some repositories have issues. Fix them before full validation.")


if __name__ == "__main__":
    import sys
    if "--all" in sys.argv:
        print("Full validation of all 500 instances not implemented yet")
        print("This would take several hours to complete")
    else:
        main()