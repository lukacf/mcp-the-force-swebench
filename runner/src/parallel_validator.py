#!/usr/bin/env python3
"""
Parallel SWE-Bench Validator

Validates all 500 instances using multiple GCP workers in parallel.
"""

import json
import time
import logging
import requests
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Repository complexity weights (estimated relative time)
REPO_COMPLEXITY = {
    'django/django': 3.0,           # Complex framework, many tests
    'sympy/sympy': 2.5,            # Heavy math computations
    'matplotlib/matplotlib': 2.0,   # Graphics rendering
    'scikit-learn/scikit-learn': 2.0,  # ML algorithms
    'sphinx-doc/sphinx': 1.5,      # Documentation building
    'astropy/astropy': 1.5,        # Scientific computing
    'pytest-dev/pytest': 1.2,      # Test framework
    'pydata/xarray': 1.2,          # Data structures
    'pylint-dev/pylint': 1.0,      # Static analysis
    'psf/requests': 0.8,           # Simple HTTP
    'mwaskom/seaborn': 1.0,        # Visualization
    'pallets/flask': 0.8,          # Web framework
}


class ParallelValidator:
    def __init__(self, worker_urls: List[str], max_workers_per_instance: int = 10):
        """
        Initialize parallel validator.
        
        Args:
            worker_urls: List of worker URLs (e.g., ['http://ip1:8080', 'http://ip2:8080'])
            max_workers_per_instance: Max concurrent validations per worker
        """
        self.worker_urls = worker_urls
        self.max_workers_per_instance = max_workers_per_instance
        self.results = []
        self.failures = []
        self.start_time = None
        self.processed_count = 0
        self.total_count = 0
        
    def validate_instance_on_worker(self, instance: Dict, worker_url: str, retry_count: int = 0) -> Dict:
        """Validate a single instance on a specific worker."""
        
        instance_id = instance['instance_id']
        logger.debug(f"Validating {instance_id} on {worker_url} (retry {retry_count})")
        
        try:
            # Step 1: Test with test_patch only (should fail)
            start = time.time()
            response1 = requests.post(
                f"{worker_url}/test",
                json={
                    "instance_id": instance_id,
                    "patch": instance['test_patch'],
                    "timeout": 300,
                    "test_files": self._extract_test_files(instance)
                },
                timeout=420
            )
            
            if response1.status_code != 200:
                raise Exception(f"Worker returned {response1.status_code}: {response1.text[:200]}")
                
            result1 = response1.json()
            
            # Step 2: Test with patch + test_patch (should pass)
            combined_patch = instance['patch'] + '\n' + instance['test_patch']
            response2 = requests.post(
                f"{worker_url}/test",
                json={
                    "instance_id": instance_id,
                    "patch": combined_patch,
                    "timeout": 300,
                    "test_files": self._extract_test_files(instance)
                },
                timeout=420
            )
            
            if response2.status_code != 200:
                raise Exception(f"Worker returned {response2.status_code}: {response2.text[:200]}")
                
            result2 = response2.json()
            duration = time.time() - start
            
            # Analyze results
            # Determine if tests passed based on stats
            stats1 = result1
            stats2 = result2
            
            # Tests pass if there are no failures/errors (and at least some tests ran)
            test_only_passed = (
                stats1.get('failed', 0) == 0 and 
                stats1.get('errors', 0) == 0 and
                (stats1.get('passed', 0) > 0 or stats1.get('collected', 0) > 0)
            )
            with_fix_passed = (
                stats2.get('failed', 0) == 0 and 
                stats2.get('errors', 0) == 0 and
                (stats2.get('passed', 0) > 0 or stats2.get('collected', 0) > 0)
            )
            
            # For SWE-Bench: test should fail without fix, pass with fix
            is_valid = not test_only_passed and with_fix_passed
            
            return {
                'instance_id': instance_id,
                'repo': instance['repo'],
                'valid': is_valid,
                'worker': worker_url,
                'duration': duration,
                'test_only': {
                    'passed': test_only_passed,
                    'stats': result1
                },
                'with_fix': {
                    'passed': with_fix_passed,
                    'stats': result2
                },
                'error': None if is_valid else f"Expected fail→pass, got {test_only_passed}→{with_fix_passed}"
            }
            
        except Exception as e:
            logger.error(f"Error validating {instance_id} on {worker_url}: {e}")
            return {
                'instance_id': instance_id,
                'repo': instance['repo'],
                'valid': False,
                'worker': worker_url,
                'error': str(e),
                'retry_count': retry_count
            }
    
    def _extract_test_files(self, instance: Dict) -> List[str]:
        """Extract test files from instance."""
        # Import the extraction logic
        from evaluator import extract_test_files_from_patch
        return extract_test_files_from_patch(instance['test_patch'])
    
    def distribute_load(self, instances: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Distribute instances across workers based on repository complexity.
        
        Returns:
            Dict mapping worker_url to list of instances
        """
        # Calculate total complexity
        total_complexity = sum(
            REPO_COMPLEXITY.get(inst['repo'], 1.0) 
            for inst in instances
        )
        
        # Target complexity per worker
        target_per_worker = total_complexity / len(self.worker_urls)
        
        # Group instances by repository
        by_repo = defaultdict(list)
        for inst in instances:
            by_repo[inst['repo']].append(inst)
        
        # Sort repos by total complexity (descending)
        repo_complexities = []
        for repo, insts in by_repo.items():
            complexity = REPO_COMPLEXITY.get(repo, 1.0) * len(insts)
            repo_complexities.append((repo, complexity, insts))
        repo_complexities.sort(key=lambda x: x[1], reverse=True)
        
        # Distribute using bin packing algorithm
        worker_assignments = {url: [] for url in self.worker_urls}
        worker_loads = {url: 0.0 for url in self.worker_urls}
        
        for repo, complexity, insts in repo_complexities:
            # Find worker with least load
            min_worker = min(worker_loads.items(), key=lambda x: x[1])[0]
            
            # Assign all instances of this repo to the same worker (cache efficiency)
            worker_assignments[min_worker].extend(insts)
            worker_loads[min_worker] += complexity
            
            logger.info(f"Assigned {repo} ({len(insts)} instances, complexity {complexity:.1f}) to {min_worker}")
        
        # Log distribution
        for worker, load in worker_loads.items():
            count = len(worker_assignments[worker])
            logger.info(f"{worker}: {count} instances, load {load:.1f}")
            
        return worker_assignments
    
    def validate_all(self, instances: List[Dict], max_retries: int = 2) -> Dict[str, Any]:
        """
        Validate all instances in parallel across workers.
        
        Returns:
            Summary dict with results
        """
        self.start_time = time.time()
        self.total_count = len(instances)
        self.processed_count = 0
        
        logger.info(f"Starting validation of {len(instances)} instances on {len(self.worker_urls)} workers")
        
        # Distribute load
        assignments = self.distribute_load(instances)
        
        # Track results
        all_results = []
        failed_instances = []
        
        # Process each worker's assignments
        with ThreadPoolExecutor(max_workers=len(self.worker_urls) * self.max_workers_per_instance) as executor:
            futures = []
            
            # Submit all validations
            for worker_url, worker_instances in assignments.items():
                for instance in worker_instances:
                    future = executor.submit(
                        self.validate_instance_on_worker,
                        instance,
                        worker_url
                    )
                    futures.append((future, instance, worker_url))
            
            # Process results as they complete
            for future, instance, worker_url in futures:
                try:
                    result = future.result(timeout=420)
                    all_results.append(result)
                    
                    self.processed_count += 1
                    self._log_progress(result)
                    
                    # Track failures for retry
                    if not result.get('valid', False) and 'error' in result:
                        failed_instances.append((instance, result))
                        
                except Exception as e:
                    logger.error(f"Failed to get result for {instance['instance_id']}: {e}")
                    failed_instances.append((instance, {'error': str(e)}))
                    self.processed_count += 1
        
        # Retry failed instances
        if failed_instances and max_retries > 0:
            logger.info(f"Retrying {len(failed_instances)} failed instances...")
            retry_results = self._retry_failed(failed_instances, max_retries)
            all_results.extend(retry_results)
        
        # Generate summary
        duration = time.time() - self.start_time
        return self._generate_summary(all_results, duration)
    
    def _retry_failed(self, failed_instances: List[tuple], max_retries: int) -> List[Dict]:
        """Retry failed instances on different workers."""
        retry_results = []
        
        with ThreadPoolExecutor(max_workers=len(self.worker_urls)) as executor:
            futures = []
            
            for instance, original_result in failed_instances:
                # Pick a different worker if possible
                original_worker = original_result.get('worker')
                available_workers = [w for w in self.worker_urls if w != original_worker]
                if not available_workers:
                    available_workers = self.worker_urls
                    
                retry_worker = random.choice(available_workers)
                retry_count = original_result.get('retry_count', 0) + 1
                
                if retry_count <= max_retries:
                    future = executor.submit(
                        self.validate_instance_on_worker,
                        instance,
                        retry_worker,
                        retry_count
                    )
                    futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=420)
                    retry_results.append(result)
                    self._log_progress(result)
                except Exception as e:
                    logger.error(f"Retry failed: {e}")
                    
        return retry_results
    
    def _log_progress(self, result: Dict):
        """Log progress with ETA."""
        status = "PASSED" if result.get('valid', False) else "FAILED"
        elapsed = time.time() - self.start_time
        rate = self.processed_count / elapsed if elapsed > 0 else 0
        eta = (self.total_count - self.processed_count) / rate if rate > 0 else 0
        
        logger.info(
            f"[{self.processed_count}/{self.total_count}] "
            f"{result['instance_id']} {status} "
            f"({result.get('duration', 0):.1f}s) on {result.get('worker', 'unknown')} "
            f"[Rate: {rate:.1f}/s, ETA: {eta:.0f}s]"
        )
    
    def _generate_summary(self, results: List[Dict], duration: float) -> Dict[str, Any]:
        """Generate validation summary."""
        valid_count = sum(1 for r in results if r.get('valid', False))
        
        # Group by repository
        by_repo = defaultdict(lambda: {'total': 0, 'valid': 0, 'errors': []})
        for r in results:
            repo = r['repo']
            by_repo[repo]['total'] += 1
            if r.get('valid', False):
                by_repo[repo]['valid'] += 1
            elif 'error' in r:
                by_repo[repo]['errors'].append(r['instance_id'])
        
        # Worker statistics
        worker_stats = Counter(r.get('worker', 'unknown') for r in results)
        
        summary = {
            'total_instances': len(results),
            'valid_instances': valid_count,
            'invalid_instances': len(results) - valid_count,
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            'instances_per_second': len(results) / duration if duration > 0 else 0,
            'by_repository': dict(by_repo),
            'by_worker': dict(worker_stats),
            'validation_rate': valid_count / len(results) * 100 if results else 0,
            'results': results
        }
        
        # Save results
        with open('parallel_validation_results.json', 'w') as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"\nValidation complete in {duration/60:.1f} minutes")
        logger.info(f"Valid: {valid_count}/{len(results)} ({summary['validation_rate']:.1f}%)")
        
        return summary


def main():
    """Run parallel validation with configuration."""
    import sys
    
    # Load configuration (created by deploy script)
    if '--config' in sys.argv:
        config_file = sys.argv[sys.argv.index('--config') + 1]
    else:
        config_file = 'worker_config.json'
        
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            worker_urls = config['worker_urls']
    except:
        logger.error(f"Could not load config from {config_file}")
        logger.info("Using default single worker")
        worker_urls = ['http://35.209.45.223:8080']
    
    # Load instances
    instances = []
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instances.append(json.loads(line))
    
    # Run validation
    validator = ParallelValidator(worker_urls)
    summary = validator.validate_all(instances)
    
    # Print summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Total: {summary['total_instances']}")
    print(f"Valid: {summary['valid_instances']} ({summary['validation_rate']:.1f}%)")
    print(f"Time: {summary['duration_minutes']:.1f} minutes")
    print(f"Rate: {summary['instances_per_second']:.1f} instances/second")
    
    print("\nBy Repository:")
    for repo, stats in sorted(summary['by_repository'].items()):
        rate = stats['valid'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {repo:30} {stats['valid']:3}/{stats['total']:3} ({rate:5.1f}%)")
        

if __name__ == "__main__":
    main()