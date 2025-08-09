#!/usr/bin/env python3
"""Validate that all SWE-Bench instances can be evaluated correctly."""

import json
import logging
import time
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from evaluator import evaluate_patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_instance(instance):
    """Validate a single instance with empty patch and known patch."""
    instance_id = instance['instance_id']
    
    try:
        # Test 1: Empty patch should fail
        start = time.time()
        result_empty = evaluate_patch(instance, "")
        duration_empty = time.time() - start
        
        # Test 2: Known patch should pass
        start = time.time()
        result_known = evaluate_patch(instance, instance['patch'])
        duration_known = time.time() - start
        
        # Analyze results
        empty_correct = not result_empty['passed']  # Should fail
        known_correct = result_known['passed']       # Should pass
        
        return {
            'instance_id': instance_id,
            'repo': instance['repo'],
            'status': 'success' if (empty_correct and known_correct) else 'failure',
            'empty_patch': {
                'passed': result_empty['passed'],
                'correct': empty_correct,
                'duration': duration_empty,
                'stats': result_empty.get('stats', {})
            },
            'known_patch': {
                'passed': result_known['passed'],
                'correct': known_correct,
                'duration': duration_known,
                'stats': result_known.get('stats', {})
            },
            'error': None if (empty_correct and known_correct) else 
                     f"Empty: {result_empty['passed']} (should be False), Known: {result_known['passed']} (should be True)"
        }
        
    except Exception as e:
        return {
            'instance_id': instance_id,
            'repo': instance['repo'],
            'status': 'error',
            'error': str(e)
        }


def main():
    # Load all instances
    instances = []
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instances.append(json.loads(line))
    
    print(f"Loaded {len(instances)} SWE-Bench instances")
    print("="*70)
    
    # Group by repository
    by_repo = defaultdict(list)
    for inst in instances:
        by_repo[inst['repo']].append(inst)
    
    print("Instances by repository:")
    for repo, insts in sorted(by_repo.items()):
        print(f"  {repo:30} {len(insts):3} instances")
    print()
    
    # Validation strategy:
    # 1. Test 2 random instances from each repo first (quick validation)
    # 2. If those pass, test all instances in batches
    
    print("Phase 1: Quick validation (2 instances per repo)")
    print("-"*70)
    
    quick_test_instances = []
    for repo, insts in by_repo.items():
        # Take up to 2 random instances from each repo
        sample_size = min(2, len(insts))
        quick_test_instances.extend(random.sample(insts, sample_size))
    
    results = []
    failures = []
    
    # Test quick samples with limited concurrency
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_instance = {
            executor.submit(validate_instance, inst): inst 
            for inst in quick_test_instances
        }
        
        for future in as_completed(future_to_instance):
            result = future.result()
            results.append(result)
            
            status_symbol = "✅" if result['status'] == 'success' else "❌"
            print(f"{status_symbol} {result['instance_id']:50} {result['status']:10}")
            
            if result['status'] != 'success':
                failures.append(result)
                if result.get('error'):
                    print(f"   Error: {result['error']}")
    
    # Analyze quick test results
    print("\nPhase 1 Summary:")
    print(f"  Tested: {len(results)}")
    print(f"  Success: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"  Failed: {len(failures)}")
    
    if failures:
        print("\nFailures by repository:")
        failure_repos = defaultdict(list)
        for f in failures:
            failure_repos[f['repo']].append(f)
        
        for repo, fails in failure_repos.items():
            print(f"\n  {repo}:")
            for f in fails[:3]:  # Show first 3 failures
                print(f"    - {f['instance_id']}: {f.get('error', 'Unknown error')}")
    
    # Save results
    with open('validation_results.json', 'w') as f:
        json.dump({
            'phase': 'quick_test',
            'total_instances': len(instances),
            'tested': len(results),
            'success': sum(1 for r in results if r['status'] == 'success'),
            'failures': failures
        }, f, indent=2)
    
    print("\nResults saved to validation_results.json")
    
    # Decide whether to continue with full validation
    success_rate = sum(1 for r in results if r['status'] == 'success') / len(results)
    print(f"\nSuccess rate: {success_rate:.1%}")
    
    if success_rate < 0.8:
        print("\n⚠️  Success rate too low. Fix issues before running full validation.")
        return
    
    print("\n✅ Quick validation passed! Ready for full validation.")
    print("\nTo run full validation on all 500 instances:")
    print("  python validate_all_instances.py --full")
    

if __name__ == "__main__":
    import sys
    if "--full" in sys.argv:
        print("Full validation not implemented yet")
    else:
        main()