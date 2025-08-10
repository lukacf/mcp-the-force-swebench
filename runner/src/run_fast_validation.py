#!/usr/bin/env python3
"""Fast parallel validation with reduced concurrency."""

import json
import time
from parallel_validator import ParallelValidator

# Load instances
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        instances.append(json.loads(line))

# Load worker config
with open('worker_config.json', 'r') as f:
    config = json.load(f)
    worker_urls = config['worker_urls']

print(f"Starting fast validation of {len(instances)} instances on {len(worker_urls)} workers")
print("="*70)

# Use reduced concurrency for better performance
validator = ParallelValidator(worker_urls, max_workers_per_instance=5)  # Reduced from 10

# Run validation
start = time.time()
summary = validator.validate_all(instances, max_retries=1)  # Reduced retries
duration = time.time() - start

print(f"\n{'='*70}")
print(f"VALIDATION COMPLETE in {duration/60:.1f} minutes")
print(f"Valid: {summary['valid_instances']}/{summary['total_instances']} ({summary['validation_rate']:.1f}%)")
print(f"Rate: {summary['instances_per_second']:.2f} instances/second")

# Show failed repos
if summary['validation_rate'] < 100:
    print("\nFailed instances by repository:")
    for repo, stats in sorted(summary['by_repository'].items()):
        if stats['valid'] < stats['total']:
            print(f"  {repo}: {stats['valid']}/{stats['total']} valid")