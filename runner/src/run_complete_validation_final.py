#!/usr/bin/env python3
"""Run complete validation of all 499 SWE-Bench instances."""

import asyncio
import json
import logging
import time
from datetime import datetime
from collections import defaultdict
import aiohttp
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Worker URLs (only active workers, excluding terminated worker-5)
WORKER_URLS = [
    "http://34.44.234.143:8080",   # swe-bench-worker-1
    "http://35.239.238.137:8080",  # swe-bench-worker-2
    "http://34.41.233.120:8080",   # swe-bench-worker-3
    "http://34.44.241.183:8080",   # swe-bench-worker-4
    "http://34.59.30.169:8080",    # swe-bench-worker-6
    "http://34.123.9.23:8080",     # swe-bench-worker-7
    "http://34.70.1.155:8080",     # swe-bench-worker-8
]

# Repository complexity weights
REPO_COMPLEXITY = {
    'django/django': 3.0,
    'sympy/sympy': 2.5,
    'matplotlib/matplotlib': 2.0,
    'scikit-learn/scikit-learn': 2.0,
    'sphinx-doc/sphinx': 1.5,
    'astropy/astropy': 1.5,
    'pytest-dev/pytest': 1.2,
    'pydata/xarray': 1.2,
    'pylint-dev/pylint': 1.0,
    'psf/requests': 0.8,
    'mwaskom/seaborn': 1.0,
    'pallets/flask': 0.8,
}

# Load instances from JSONL file
all_instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        all_instances.append(json.loads(line))

# Take exactly 499 instances (or all if less)
instances = all_instances[:499]

print(f"Loaded {len(instances)} instances")
print(f"Using {len(WORKER_URLS)} workers")

async def validate_instance(session: aiohttp.ClientSession, instance: Dict[str, Any], 
                          worker_url: str, timeout: int = 150) -> Dict[str, Any]:
    """Validate a single instance on a worker."""
    start_time = time.time()
    
    # Extract test files from test_patch
    test_files = []
    if 'test_patch' in instance and instance['test_patch']:
        import re
        lines = instance['test_patch'].split('\n')
        for line in lines:
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                file_path = line[6:]
                if 'test' in file_path and file_path.endswith('.py'):
                    test_files.append(file_path)
    
    test_files = list(set(test_files))
    
    payload = {
        "instance_id": instance["instance_id"],
        "patch": instance.get("patch", ""),
        "test_files": test_files,
        "timeout": timeout
    }
    
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with session.post(f"{worker_url}/test", json=payload, timeout=timeout_config) as response:
            result = await response.json()
            duration = time.time() - start_time
            
            # Determine if passed
            passed = (
                result.get('failed', 0) == 0 and 
                result.get('errors', 0) == 0 and
                (result.get('passed', 0) > 0 or result.get('collected', 0) > 0)
            )
            
            return {
                "instance_id": instance["instance_id"],
                "passed": passed,
                "duration": duration,
                "worker": worker_url,
                "details": result
            }
    
    except Exception as e:
        logger.error(f"Error validating {instance['instance_id']} on {worker_url}: {e}")
        return {
            "instance_id": instance["instance_id"],
            "passed": False,
            "duration": time.time() - start_time,
            "worker": worker_url,
            "error": str(e)
        }

async def worker_task(worker_url: str, instance_queue: asyncio.Queue, 
                     results_queue: asyncio.Queue, session: aiohttp.ClientSession):
    """Worker task that processes instances from the queue."""
    while True:
        try:
            instance = await instance_queue.get()
            if instance is None:
                break
                
            result = await validate_instance(session, instance, worker_url)
            await results_queue.put(result)
            
        except Exception as e:
            logger.error(f"Worker {worker_url} error: {e}")

async def assign_instances_to_workers(instances: List[Dict]) -> Dict[str, List[Dict]]:
    """Assign instances to workers based on repository and complexity."""
    # Group instances by repository
    by_repo = defaultdict(list)
    for inst in instances:
        repo = inst['repo']
        by_repo[repo].append(inst)
    
    # Calculate total complexity for each repo
    repo_loads = []
    for repo, repo_instances in by_repo.items():
        complexity = REPO_COMPLEXITY.get(repo, 1.0)
        total_load = len(repo_instances) * complexity
        repo_loads.append((repo, repo_instances, total_load))
    
    # Sort by load (heaviest first)
    repo_loads.sort(key=lambda x: x[2], reverse=True)
    
    # Initialize worker assignments
    worker_assignments = {url: [] for url in WORKER_URLS}
    worker_loads = {url: 0.0 for url in WORKER_URLS}
    
    # Assign repositories to workers
    for repo, repo_instances, load in repo_loads:
        # Find worker with minimum load
        min_worker = min(worker_loads.items(), key=lambda x: x[1])[0]
        worker_assignments[min_worker].extend(repo_instances)
        worker_loads[min_worker] += load
        logger.info(f"Assigned {repo} ({len(repo_instances)} instances, complexity {load:.1f}) to {min_worker}")
    
    # Log final assignments
    for worker, load in worker_loads.items():
        logger.info(f"{worker}: {len(worker_assignments[worker])} instances, load {load:.1f}")
    
    return worker_assignments

async def main():
    """Main validation function."""
    logger.info(f"Starting validation of {len(instances)} instances on {len(WORKER_URLS)} workers")
    
    # Assign instances to workers
    worker_assignments = await assign_instances_to_workers(instances)
    
    # Create output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"validation_results_{timestamp}.json"
    
    results = []
    passed = 0
    failed = 0
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # Process each worker's assignments
        tasks = []
        for worker_url, worker_instances in worker_assignments.items():
            for instance in worker_instances:
                task = validate_instance(session, instance, worker_url)
                tasks.append(task)
        
        # Process results as they complete
        for i, future in enumerate(asyncio.as_completed(tasks)):
            result = await future
            results.append(result)
            
            if result.get('passed', False):
                passed += 1
                status = "PASSED"
            else:
                failed += 1
                status = "FAILED"
            
            completed = i + 1
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (len(instances) - completed) / rate if rate > 0 else 0
            pass_rate = (passed / completed * 100) if completed > 0 else 0
            
            logger.info(f"[{completed}/{len(instances)}] {result['instance_id']} {status} "
                       f"({result['duration']:.1f}s) on {result['worker']} "
                       f"[Rate: {rate:.1f}/s, ETA: {eta:.0f}s]")
            
            # Save intermediate results every 50 instances
            if completed % 50 == 0:
                with open(output_file, 'w') as f:
                    json.dump({
                        "completed": completed,
                        "total": len(instances),
                        "passed": passed,
                        "failed": failed,
                        "pass_rate": pass_rate,
                        "results": results
                    }, f, indent=2)
    
    # Save final results
    final_pass_rate = (passed / len(results) * 100) if results else 0
    with open(output_file, 'w') as f:
        json.dump({
            "completed": len(results),
            "total": len(instances),
            "passed": passed,
            "failed": failed,
            "pass_rate": final_pass_rate,
            "results": results,
            "duration": time.time() - start_time
        }, f, indent=2)
    
    # Print summary
    print(f"\n" + "="*60)
    print(f"VALIDATION COMPLETE")
    print(f"Total: {len(results)}/{len(instances)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass rate: {final_pass_rate:.1f}%")
    print(f"Duration: {time.time() - start_time:.1f}s")
    print(f"Results saved to: {output_file}")
    print("="*60)
    
    # Print per-repo summary
    repo_stats = defaultdict(lambda: {'passed': 0, 'failed': 0})
    for result in results:
        repo = result['instance_id'].split('__')[0].replace('_', '/')
        if result.get('passed', False):
            repo_stats[repo]['passed'] += 1
        else:
            repo_stats[repo]['failed'] += 1
    
    print(f"\n{'Repository':<30} {'Passed':>8} {'Failed':>8} {'Pass Rate':>10}")
    print("-" * 60)
    for repo in sorted(repo_stats.keys()):
        stats = repo_stats[repo]
        total = stats['passed'] + stats['failed']
        repo_pass_rate = (stats['passed'] / total * 100) if total > 0 else 0
        print(f"{repo:<30} {stats['passed']:>8} {stats['failed']:>8} {repo_pass_rate:>9.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
