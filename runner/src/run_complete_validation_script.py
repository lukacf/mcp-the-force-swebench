
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

# Worker URLs (only active workers)
WORKER_URLS = ['http://34.44.234.143:8080', 'http://35.239.238.137:8080', 'http://34.41.233.120:8080', 'http://34.44.241.183:8080', 'http://34.59.30.169:8080', 'http://34.123.9.23:8080', 'http://34.70.1.155:8080']

# Load instances
with open('../swebench_instances.json', 'r') as f:
    instances = json.load(f)

# Filter to get exactly 499 instances (excluding the deprecated one)
instances = [i for i in instances if i["instance_id"] != "deprecated_instance"]
instances = instances[:499]  # Ensure we have exactly 499

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
        # Look for test file paths in the patch
        lines = instance['test_patch'].split('\n')
        for line in lines:
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                file_path = line[6:]
                if 'test' in file_path and file_path.endswith('.py'):
                    test_files.append(file_path)
    
    # Remove duplicates
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
            
            # Determine if passed (no failures and no errors)
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
            if instance is None:  # Sentinel value
                break
                
            result = await validate_instance(session, instance, worker_url)
            await results_queue.put(result)
            
        except Exception as e:
            logger.error(f"Worker {worker_url} error: {e}")

async def progress_monitor(results_queue: asyncio.Queue, total: int, output_file: str):
    """Monitor progress and save results."""
    results = []
    passed = 0
    failed = 0
    start_time = time.time()
    
    while len(results) < total:
        try:
            result = await asyncio.wait_for(results_queue.get(), timeout=1.0)
            results.append(result)
            
            if result.get('passed', False):
                passed += 1
                status = "PASSED"
            else:
                failed += 1
                status = "FAILED"
            
            completed = len(results)
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            pass_rate = (passed / completed * 100) if completed > 0 else 0
            
            logger.info(f"[{completed}/{total}] {result['instance_id']} {status} "
                       f"({result['duration']:.1f}s) on {result['worker']} "
                       f"[Rate: {rate:.1f}/s, ETA: {eta:.0f}s, Pass rate: {pass_rate:.1f}%]")
            
            # Save intermediate results
            if completed % 10 == 0:
                with open(output_file, 'w') as f:
                    json.dump({
                        "completed": completed,
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "pass_rate": pass_rate,
                        "results": results
                    }, f, indent=2)
                    
        except asyncio.TimeoutError:
            continue
    
    # Save final results
    with open(output_file, 'w') as f:
        json.dump({
            "completed": len(results),
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / len(results) * 100) if results else 0,
            "results": results,
            "duration": time.time() - start_time
        }, f, indent=2)
    
    return results

async def main():
    """Main validation function."""
    logger.info(f"Starting validation of {len(instances)} instances on {len(WORKER_URLS)} workers")
    
    # Create queues
    instance_queue = asyncio.Queue()
    results_queue = asyncio.Queue()
    
    # Add all instances to the queue
    for instance in instances:
        await instance_queue.put(instance)
    
    # Add sentinel values
    for _ in WORKER_URLS:
        await instance_queue.put(None)
    
    # Create output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"validation_results_{timestamp}.json"
    
    # Start validation
    async with aiohttp.ClientSession() as session:
        # Create worker tasks
        worker_tasks = [
            asyncio.create_task(worker_task(worker_url, instance_queue, results_queue, session))
            for worker_url in WORKER_URLS
        ]
        
        # Create progress monitor task
        monitor_task = asyncio.create_task(
            progress_monitor(results_queue, len(instances), output_file)
        )
        
        # Wait for all workers to complete
        await asyncio.gather(*worker_tasks)
        
        # Wait for monitor to process all results
        results = await monitor_task
    
    # Print summary
    passed = sum(1 for r in results if r.get('passed', False))
    failed = len(results) - passed
    pass_rate = (passed / len(results) * 100) if results else 0
    
    print(f"
" + "="*60)
    print(f"VALIDATION COMPLETE")
    print(f"Total: {len(results)}/{len(instances)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass rate: {pass_rate:.1f}%")
    print(f"Results saved to: {output_file}")
    print("="*60)
    
    # Print per-repo summary
    repo_stats = defaultdict(lambda: {'passed': 0, 'failed': 0})
    for result in results:
        repo = result['instance_id'].split('__')[0]
        if result.get('passed', False):
            repo_stats[repo]['passed'] += 1
        else:
            repo_stats[repo]['failed'] += 1
    
    print(f"
{'Repository':<30} {'Passed':>8} {'Failed':>8} {'Pass Rate':>10}")
    print("-" * 60)
    for repo in sorted(repo_stats.keys()):
        stats = repo_stats[repo]
        total = stats['passed'] + stats['failed']
        repo_pass_rate = (stats['passed'] / total * 100) if total > 0 else 0
        print(f"{repo:<30} {stats['passed']:>8} {stats['failed']:>8} {repo_pass_rate:>9.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
