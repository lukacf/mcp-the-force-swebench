#!/usr/bin/env python3
"""Resume validation with better error handling and progress saving."""

import json
import logging
import time
import os
from datetime import datetime
from parallel_validator import ParallelValidator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('validation_resume.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load instances
instances = []
with open('../swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        instances.append(json.loads(line))

# Load worker config
with open('worker_config.json', 'r') as f:
    config = json.load(f)
    worker_urls = config['worker_urls']

# Check what was already processed
processed_ids = set()
if os.path.exists('parallel_validation.log'):
    with open('parallel_validation.log', 'r') as f:
        for line in f:
            if 'PASSED' in line or 'FAILED' in line:
                # Extract instance ID from log line
                parts = line.split('] ')
                if len(parts) >= 2:
                    instance_part = parts[1].split(' ')[0]
                    processed_ids.add(instance_part)

logger.info(f"Found {len(processed_ids)} already processed instances")

# Filter out already processed
remaining_instances = [inst for inst in instances if inst['instance_id'] not in processed_ids]
logger.info(f"Remaining instances to process: {len(remaining_instances)}")

# Save checkpoint of what was already done
checkpoint = {
    'timestamp': datetime.now().isoformat(),
    'total_instances': len(instances),
    'processed': len(processed_ids),
    'remaining': len(remaining_instances),
    'processed_ids': list(processed_ids)
}

with open('validation_checkpoint.json', 'w') as f:
    json.dump(checkpoint, f, indent=2)

if remaining_instances:
    logger.info(f"Starting validation of {len(remaining_instances)} remaining instances on {len(worker_urls)} workers")
    logger.info("="*70)
    
    # Use reduced concurrency and save results periodically
    validator = ParallelValidator(worker_urls, max_workers_per_instance=3)  # Further reduced
    
    # Add result saving callback
    validator.save_interval = 10  # Save every 10 instances
    validator.results_file = f'validation_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    try:
        # Run validation with better error handling
        start = time.time()
        summary = validator.validate_all(remaining_instances, max_retries=1)
        duration = time.time() - start
        
        logger.info(f"\n{'='*70}")
        logger.info(f"VALIDATION COMPLETE in {duration/60:.1f} minutes")
        logger.info(f"Valid: {summary['valid_instances']}/{summary['total_instances']} ({summary['validation_rate']:.1f}%)")
        logger.info(f"Rate: {summary['instances_per_second']:.2f} instances/second")
        
        # Save final results
        final_results = {
            'timestamp': datetime.now().isoformat(),
            'total_instances': len(instances),
            'newly_processed': len(remaining_instances),
            'previously_processed': len(processed_ids),
            'summary': summary,
            'duration_minutes': duration/60
        }
        
        with open(f'final_validation_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
            json.dump(final_results, f, indent=2)
            
    except Exception as e:
        logger.error(f"Validation failed with error: {e}", exc_info=True)
        raise
else:
    logger.info("All instances have already been processed!")
    logger.info("Check parallel_validation.log for results.")