#!/usr/bin/env python3
"""
Quick test of psf/requests instances with available workers.
Tests if the Python version fix is working.
"""

import json
import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Available workers
working_workers = ['http://34.123.9.23:8080', 'http://34.70.1.155:8080']

# Test 3 psf/requests instances
test_instances = [
    "psf__requests-1142",
    "psf__requests-2931",
    "psf__requests-1724"
]

# Load instance data
instances = {}
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] in test_instances:
            instances[inst['instance_id']] = inst

logger.info(f"Testing {len(instances)} psf/requests instances on {len(working_workers)} workers...")
logger.info("These workers should have the fixed tester with python -m pytest")

# Test each instance
results = []
for idx, (instance_id, instance) in enumerate(instances.items()):
    worker_url = working_workers[idx % len(working_workers)]
    logger.info(f"\n[{idx+1}/{len(instances)}] Testing {instance_id} on {worker_url}")
    
    try:
        # First test: with test_patch only (should fail)
        logger.info("  Step 1: Testing with test_patch only (should fail)...")
        response1 = requests.post(
            f"{worker_url}/test",
            json={
                "instance_id": instance_id,
                "patch": instance['test_patch'],
                "timeout": 300
            },
            timeout=420
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            logger.info(f"    Result: passed={result1.get('passed', 0)}, "
                       f"failed={result1.get('failed', 0)}, "
                       f"errors={result1.get('errors', 0)}")
            test_only_passed = (
                result1.get('failed', 0) == 0 and 
                result1.get('errors', 0) == 0 and
                result1.get('passed', 0) > 0
            )
        else:
            logger.error(f"    Failed with status {response1.status_code}")
            test_only_passed = False
            result1 = {'error': f"HTTP {response1.status_code}"}
        
        # Second test: with patch + test_patch (should pass)
        logger.info("  Step 2: Testing with patch + test_patch (should pass)...")
        combined_patch = instance['patch'] + '\n' + instance['test_patch']
        response2 = requests.post(
            f"{worker_url}/test",
            json={
                "instance_id": instance_id,
                "patch": combined_patch,
                "timeout": 300
            },
            timeout=420
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            logger.info(f"    Result: passed={result2.get('passed', 0)}, "
                       f"failed={result2.get('failed', 0)}, "
                       f"errors={result2.get('errors', 0)}")
            with_fix_passed = (
                result2.get('failed', 0) == 0 and 
                result2.get('errors', 0) == 0 and
                result2.get('passed', 0) > 0
            )
        else:
            logger.error(f"    Failed with status {response2.status_code}")
            with_fix_passed = False
            result2 = {'error': f"HTTP {response2.status_code}"}
        
        # Check validation result
        is_valid = not test_only_passed and with_fix_passed
        logger.info(f"  Validation result: {'VALID' if is_valid else 'INVALID'} "
                   f"(test_only_passed={test_only_passed}, with_fix_passed={with_fix_passed})")
        
        results.append({
            'instance_id': instance_id,
            'worker': worker_url,
            'valid': is_valid,
            'test_only': result1,
            'with_fix': result2
        })
        
    except Exception as e:
        logger.error(f"  Exception: {e}")
        results.append({
            'instance_id': instance_id,
            'worker': worker_url,
            'error': str(e)
        })

# Summary
logger.info("\n" + "="*70)
logger.info("TEST SUMMARY")
logger.info("="*70)

valid = [r for r in results if r.get('valid', False)]
invalid = [r for r in results if not r.get('valid', False) and 'error' not in r]
errors = [r for r in results if 'error' in r]

logger.info(f"Valid: {len(valid)}/{len(results)}")
logger.info(f"Invalid: {len(invalid)}/{len(results)}")
logger.info(f"Errors: {len(errors)}/{len(results)}")

if valid:
    logger.info("\nValid instances:")
    for r in valid:
        logger.info(f"  ✅ {r['instance_id']}")

if invalid:
    logger.info("\nInvalid instances:")
    for r in invalid:
        logger.info(f"  ❌ {r['instance_id']}")

if errors:
    logger.info("\nError instances:")
    for r in errors:
        logger.info(f"  ⚠️  {r['instance_id']}: {r['error']}")

# Check for Python version issues
logger.info("\nChecking for Python version issues...")
python_errors = 0
for r in results:
    if 'test_only' in r and isinstance(r['test_only'], dict):
        log_tail = r['test_only'].get('log_tail', '')
        if 'MutableMapping' in log_tail or 'collections.abc' in log_tail:
            logger.warning(f"  Python version issue detected in {r['instance_id']}")
            python_errors += 1

if python_errors == 0:
    logger.info("  ✅ No Python version issues detected!")
else:
    logger.warning(f"  ⚠️  {python_errors} instances still have Python version issues")

# Save results
with open('psf_requests_test_results.json', 'w') as f:
    json.dump({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'workers_used': working_workers,
        'instances_tested': len(results),
        'valid': len(valid),
        'invalid': len(invalid),
        'errors': len(errors),
        'python_version_issues': python_errors,
        'results': results
    }, f, indent=2)

logger.info(f"\nResults saved to psf_requests_test_results.json")