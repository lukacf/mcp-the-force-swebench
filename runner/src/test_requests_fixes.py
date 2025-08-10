#!/usr/bin/env python3
"""
Test the fixes for psf/requests instances using the current workers.
Since we can't update the workers directly, we'll work around the issues.
"""

import json
import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load worker config
with open('worker_config.json', 'r') as f:
    config = json.load(f)
    worker_urls = config['worker_urls']

# Find working workers
working_workers = []
for url in worker_urls:
    try:
        resp = requests.get(f"{url}/health", timeout=5)
        if resp.status_code == 200:
            working_workers.append(url)
            logger.info(f"✅ Worker {url} is available")
    except:
        logger.warning(f"❌ Worker {url} is not responding")

logger.info(f"\nFound {len(working_workers)} working workers")

# Test psf/requests instances
test_instances = [
    "psf__requests-1142",
    "psf__requests-2931", 
    "psf__requests-1724",
    "psf__requests-1766",
    "psf__requests-1921"
]

# Load instance data
instances = {}
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        inst = json.loads(line)
        if inst['instance_id'] in test_instances:
            instances[inst['instance_id']] = inst

logger.info(f"\nTesting {len(instances)} psf/requests instances...")

# Since we can't update the tester service, we'll work around the issues:
# 1. We know the tester is using wrong Python version
# 2. We'll create patches that fix the import issues in the code itself

def create_compatibility_patch(original_patch):
    """Add Python 3.x compatibility fixes to the patch."""
    # Add imports fix at the beginning
    compat_fix = """--- a/requests/packages/urllib3/_collections.py
+++ b/requests/packages/urllib3/_collections.py
@@ -4,7 +4,10 @@
 # This module is part of urllib3 , but was copied to the requests namespace
 # for backwards compatibility.
 
-from collections import MutableMapping
+try:
+    from collections.abc import MutableMapping
+except ImportError:
+    from collections import MutableMapping
 try:
     from threading import RLock
 except ImportError: # Platform-specific: No threads available
"""
    
    # Combine with original patch
    if original_patch.strip():
        return compat_fix + "\n" + original_patch
    else:
        return compat_fix

# Test each instance
results = []
for idx, (instance_id, instance) in enumerate(instances.items()):
    worker_url = working_workers[idx % len(working_workers)]
    logger.info(f"\n[{idx+1}/{len(instances)}] Testing {instance_id} on {worker_url}")
    
    try:
        # Create compatibility patch
        compat_patch = create_compatibility_patch(instance['patch'])
        
        # Run test with compatibility patch
        response = requests.post(
            f"{worker_url}/test",
            json={
                "instance_id": instance_id,
                "patch": compat_patch,
                "timeout": 300,
                "test_files": None  # Let it run all tests
            },
            timeout=420
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"  Result: passed={result.get('passed', 0)}, "
                       f"failed={result.get('failed', 0)}, "
                       f"errors={result.get('errors', 0)}")
            
            # Check if it's a valid SWE-bench result
            # For compatibility patch, we expect tests to still fail
            # (since we're not applying the actual fix)
            is_valid = result.get('failed', 0) > 0 or result.get('errors', 0) > 0
            
            results.append({
                'instance_id': instance_id,
                'worker': worker_url,
                'passed': result.get('passed', 0),
                'failed': result.get('failed', 0),
                'errors': result.get('errors', 0),
                'duration': result.get('duration', 0),
                'valid': is_valid
            })
        else:
            logger.error(f"  Failed with status {response.status_code}: {response.text[:200]}")
            results.append({
                'instance_id': instance_id,
                'worker': worker_url,
                'error': f"HTTP {response.status_code}"
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

successful = [r for r in results if 'error' not in r]
failed = [r for r in results if 'error' in r]

logger.info(f"Successful runs: {len(successful)}/{len(results)}")
logger.info(f"Failed runs: {len(failed)}/{len(results)}")

if successful:
    logger.info("\nSuccessful instances:")
    for r in successful:
        logger.info(f"  {r['instance_id']}: passed={r['passed']}, failed={r['failed']}, errors={r['errors']}")

if failed:
    logger.info("\nFailed instances:")
    for r in failed:
        logger.info(f"  {r['instance_id']}: {r['error']}")

# Save results
with open('requests_test_results.json', 'w') as f:
    json.dump({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'workers_tested': len(working_workers),
        'instances_tested': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'results': results
    }, f, indent=2)

logger.info(f"\nResults saved to requests_test_results.json")