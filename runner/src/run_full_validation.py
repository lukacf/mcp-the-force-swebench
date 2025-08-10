#!/usr/bin/env python3
"""
High-level runner for parallel SWE-Bench validation.

This script provides a user-friendly interface to run the full validation.
"""

import json
import subprocess
import sys
import time
from collections import defaultdict

def analyze_instances():
    """Analyze instance distribution and complexity."""
    instances = []
    with open('../swe_bench_instances.jsonl', 'r') as f:
        for line in f:
            instances.append(json.loads(line))
    
    # Group by repository
    by_repo = defaultdict(list)
    for inst in instances:
        by_repo[inst['repo']].append(inst)
    
    print("SWE-BENCH INSTANCE ANALYSIS")
    print("="*60)
    print(f"Total instances: {len(instances)}")
    print("\nBy Repository:")
    
    total_complexity = 0
    repo_complexities = {
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
    
    for repo in sorted(by_repo.keys()):
        count = len(by_repo[repo])
        complexity = repo_complexities.get(repo, 1.0)
        total = count * complexity
        total_complexity += total
        print(f"  {repo:30} {count:3} instances (complexity: {total:6.1f})")
    
    print(f"\nTotal complexity score: {total_complexity:.1f}")
    return len(instances), by_repo


def estimate_time_and_cost(num_instances, num_workers=8):
    """Estimate validation time and cost."""
    # Assumptions:
    # - Average 4 seconds per instance validation (2 tests)
    # - 10-15 concurrent validations per worker
    # - Some overhead for coordination
    
    avg_time_per_instance = 4  # seconds
    concurrent_per_worker = 12
    total_concurrent = num_workers * concurrent_per_worker
    
    # Rough estimate
    waves = (num_instances + total_concurrent - 1) // total_concurrent
    estimated_time = waves * avg_time_per_instance + 60  # +60s for startup/coordination
    
    # Cost estimate
    cost_per_hour = 3  # c2-standard-60
    total_cost = num_workers * cost_per_hour * (estimated_time / 3600)
    
    return estimated_time, total_cost


def check_fleet_status():
    """Check if validation fleet is deployed."""
    try:
        with open('worker_config.json', 'r') as f:
            config = json.load(f)
            return config.get('worker_urls', [])
    except:
        return []


def main():
    """Main validation runner."""
    print("🚀 SWE-BENCH PARALLEL VALIDATION RUNNER")
    print("="*60)
    
    # Analyze instances
    num_instances, by_repo = analyze_instances()
    
    # Check fleet status
    worker_urls = check_fleet_status()
    
    if not worker_urls:
        print("\n⚠️  No validation fleet detected!")
        print("\nTo deploy the fleet, run:")
        print("  ../../scripts/gcp/deploy_validation_fleet.sh")
        print("\nThis will create 8 GCP instances (~$24/hour total)")
        
        response = input("\nDeploy fleet now? (y/N): ")
        if response.lower() == 'y':
            print("\nDeploying fleet...")
            subprocess.run(["../../scripts/gcp/deploy_validation_fleet.sh"], check=True)
            
            # Reload config
            worker_urls = check_fleet_status()
            if not worker_urls:
                print("❌ Failed to deploy fleet")
                return
        else:
            print("Aborted.")
            return
    
    num_workers = len(worker_urls)
    print(f"\n✅ Fleet detected: {num_workers} workers")
    
    # Estimate time and cost
    est_time, est_cost = estimate_time_and_cost(num_instances, num_workers)
    
    print(f"\nESTIMATES:")
    print(f"  Time: {est_time/60:.1f} minutes")
    print(f"  Cost: ${est_cost:.2f}")
    print(f"  Rate: {num_instances/est_time:.1f} instances/second")
    
    print("\nVALIDATION PLAN:")
    print("  1. Each instance will be tested twice:")
    print("     - With test_patch only (should fail)")
    print("     - With patch + test_patch (should pass)")
    print("  2. Failed validations will be retried on different workers")
    print("  3. Results will be saved to parallel_validation_results.json")
    
    # Auto-start for non-interactive environments
    print("\nStarting validation automatically...")
    
    # Run validation
    print("\n" + "="*60)
    print("STARTING VALIDATION")
    print("="*60)
    
    start_time = time.time()
    
    # Run the parallel validator
    result = subprocess.run([
        sys.executable, 
        "parallel_validator.py",
        "--config", "worker_config.json"
    ])
    
    duration = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total time: {duration/60:.1f} minutes")
    print(f"Actual cost: ${num_workers * 3 * duration/3600:.2f}")
    
    # Load and display results
    try:
        with open('parallel_validation_results.json', 'r') as f:
            results = json.load(f)
            
        print(f"\nRESULTS:")
        print(f"  Valid: {results['valid_instances']}/{results['total_instances']} ({results['validation_rate']:.1f}%)")
        
        if results['validation_rate'] < 100:
            print(f"\nFailed instances by repository:")
            for repo, stats in sorted(results['by_repository'].items()):
                if stats['errors']:
                    print(f"\n  {repo}:")
                    for err in stats['errors'][:5]:  # Show first 5
                        print(f"    - {err}")
                    if len(stats['errors']) > 5:
                        print(f"    ... and {len(stats['errors'])-5} more")
    except:
        print("\n⚠️  Could not load results file")
    
    print(f"\n{'='*60}")
    print("Don't forget to destroy the fleet when done:")
    print("  ../../scripts/gcp/deploy_validation_fleet.sh --destroy")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()