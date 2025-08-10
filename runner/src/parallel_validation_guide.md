# Parallel SWE-Bench Validation Guide

## Overview

This guide describes how to validate 500 SWE-Bench instances in under 30 minutes using parallel GCP instances running the FastAPI tester service.

## Architecture

### Components

1. **Orchestrator** (Your local machine or a dedicated GCP instance)
   - Runs `parallel_validator.py`
   - Distributes work across worker instances
   - Handles retries and aggregates results
   - Monitors progress and health

2. **Worker Instances** (GCP c2-standard-60 instances)
   - Each runs the FastAPI tester service in Docker
   - Handles concurrent validation requests
   - Pre-loaded with Docker images for all repositories

3. **Load Balancer**
   - Intelligent distribution based on repository complexity
   - Keeps instances from the same repository on the same worker (cache efficiency)
   - Balances workload across all workers

### Optimal Configuration

Based on the instance distribution and complexity analysis:

```
Total instances: 500
Target time: < 30 minutes
Processing rate needed: ~17 instances/minute = 0.28 instances/second
```

#### Recommended Setup: 8-10 Worker Instances

**Why 8-10 workers?**
- Each c2-standard-60 instance can handle 10-15 concurrent validations
- Total capacity: 80-150 concurrent validations
- Provides redundancy for failures and retries
- Cost: ~$24-30 for a 30-minute run
- Leaves headroom for slower repositories

#### Worker Distribution Strategy

```python
# Complexity-weighted distribution
Worker 1: django/django (100 instances) - Heavy workload
Worker 2: django/django (100 instances) - Heavy workload  
Worker 3: django/django (31 instances) + sympy/sympy (40 instances)
Worker 4: sympy/sympy (35 instances) + matplotlib/matplotlib (34 instances)
Worker 5: scikit-learn/scikit-learn (32 instances) + sphinx-doc/sphinx (44 instances)
Worker 6: astropy/astropy (22 instances) + pydata/xarray (22 instances) + pytest-dev/pytest (19 instances)
Worker 7: pylint-dev/pylint (10 instances) + psf/requests (8 instances) + mwaskom/seaborn (2 instances) + pallets/flask (1 instance)
Worker 8: [Reserved for retries and overflow]
```

## Step-by-Step Deployment

### 1. Prepare GCP Infrastructure

```bash
# Create 8 worker instances
for i in {1..8}; do
  gcloud compute instances create swe-bench-worker-$i \
    --machine-type=c2-standard-60 \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-ssd \
    --zone=us-central1-a \
    --tags=swe-bench-worker \
    --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose
systemctl start docker
systemctl enable docker
usermod -aG docker $USER
docker pull your-registry/swe-bench-tester:latest
docker run -d --restart always -p 8080:8080 your-registry/swe-bench-tester:latest'
done

# Create firewall rule
gcloud compute firewall-rules create allow-swe-bench \
  --allow tcp:8080 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=swe-bench-worker
```

### 2. Pre-warm Worker Instances

```python
# Script to pre-warm Docker images on each worker
import concurrent.futures
import requests

def prewarm_worker(worker_ip, repos):
    """Pre-pull Docker images for assigned repositories."""
    for repo in repos:
        # Send a dummy request to trigger image pull
        requests.post(
            f"http://{worker_ip}:8080/test",
            json={
                "instance_id": f"prewarm_{repo.replace('/', '_')}",
                "patch": "",
                "timeout": 30
            },
            timeout=60
        )

# Run pre-warming in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    futures = []
    for worker in workers:
        future = executor.submit(prewarm_worker, worker.host, worker.assigned_repos)
        futures.append(future)
    concurrent.futures.wait(futures)
```

### 3. Run Validation

```bash
# Update parallel_validator.py with your worker IPs
# Then run:
python parallel_validator.py \
  --workers 8 \
  --timeout 120 \
  --max-retries 2 \
  --output validation_results_$(date +%Y%m%d_%H%M%S)
```

### 4. Monitor Progress

The validator provides real-time progress updates:
```
2024-01-15 10:00:00 - INFO - Starting validation of 500 instances across 8 workers
2024-01-15 10:00:05 - INFO - ✅ [1/500] django__django-11099 PASSED (4.2s) on worker-1 [Rate: 0.2/s, ETA: 2495s]
2024-01-15 10:00:06 - INFO - ✅ [2/500] sympy__sympy-12419 PASSED (5.1s) on worker-3 [Rate: 0.3/s, ETA: 1660s]
...
```

### 5. Handle Failures

The system automatically handles failures with:
1. **Automatic retries** (up to 2 per instance)
2. **Worker health checks** 
3. **Fallback to healthy workers**
4. **Detailed error logging**

## Cost Analysis

```
Instance type: c2-standard-60
Cost per hour: $3.06
Number of instances: 8
Duration: 0.5 hours
Total cost: 8 * $3.06 * 0.5 = $12.24

With buffer and setup time: ~$20-25
```

## Optimizations

### 1. Repository-Aware Scheduling
- Instances from the same repository go to the same worker
- Maximizes Docker layer cache hits
- Reduces git clone operations

### 2. Concurrent Processing
- Each worker handles 10-15 validations concurrently
- Non-blocking I/O for network requests
- Thread pool for CPU-bound operations

### 3. Smart Retries
- Failed validations are redistributed to healthy workers
- Exponential backoff for transient failures
- Detailed error tracking for debugging

### 4. Result Streaming
- Results saved immediately as they complete
- Can resume from partial results if interrupted
- Real-time progress monitoring

## Monitoring and Debugging

### Health Dashboard
```python
# Simple health check script
import requests
import time

while True:
    for worker in workers:
        try:
            resp = requests.get(f"http://{worker.host}:8080/health", timeout=2)
            print(f"✅ {worker.id}: OK")
        except:
            print(f"❌ {worker.id}: DOWN")
    time.sleep(10)
```

### Performance Metrics
- Average validation time per repository
- Worker utilization rates  
- Retry rates and failure patterns
- Network latency measurements

## Failure Recovery

### Common Issues and Solutions

1. **Worker instance crashes**
   - Other workers automatically take over
   - Failed validations go to retry queue

2. **Network timeouts**
   - Automatic retry with exponential backoff
   - Configurable timeout limits

3. **Docker pull failures**
   - Pre-warming prevents most issues
   - Retry on different worker if needed

4. **Memory exhaustion**
   - c2-standard-60 has 240GB RAM
   - Monitor and adjust concurrency if needed

## Post-Validation

### Results Structure
```
validation_results/
├── summary.json          # Overall statistics
├── results.jsonl         # Simple pass/fail list  
├── django__django-11099.json  # Detailed result
├── django__django-11103.json
└── ...
```

### Analysis Scripts
```python
# Count failures by repository
import json
from collections import defaultdict

failures_by_repo = defaultdict(int)
with open('results.jsonl') as f:
    for line in f:
        result = json.loads(line)
        if not result['passed']:
            instance_id = result['instance_id']
            repo = instance_id.split('__')[0].replace('_', '/')
            failures_by_repo[repo] += 1

print("Failures by repository:")
for repo, count in sorted(failures_by_repo.items()):
    print(f"  {repo}: {count}")
```

## Scaling Beyond 500 Instances

For larger validations:
1. **Add more workers** - Linear scaling up to ~50 workers
2. **Use regional distribution** - Deploy workers across multiple GCP regions
3. **Implement hierarchical orchestration** - Master orchestrator + regional sub-orchestrators
4. **Consider GKE** - Kubernetes for automatic scaling and management

## Conclusion

This architecture can reliably validate 500 SWE-Bench instances in 20-25 minutes using 8-10 GCP workers. The system is resilient to failures, provides real-time monitoring, and scales linearly with additional workers.