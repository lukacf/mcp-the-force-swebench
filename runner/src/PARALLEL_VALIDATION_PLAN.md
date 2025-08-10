# Parallel Validation Execution Plan

## Overview
Validate all 500 SWE-Bench instances using 8 parallel GCP workers in ~20-25 minutes.

## Architecture
```
┌─────────────────┐
│ Orchestrator    │
│ (local machine) │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┬────────┬────────┬────────┬────────┐
    │         │        │        │        │        │        │        │
┌───▼──┐ ┌───▼──┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐
│Work-1│ │Work-2│ │Work-3│ │Work-4│ │Work-5│ │Work-6│ │Work-7│ │Work-8│
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
 Django   Django   SymPy    MatPlot  Scikit   Mixed    Small    Retry
 (115)    (116)    (75)     (34)     Learn    repos    repos    pool
                            +Sphinx   (32)     (63)     (28)     
```

## Cost Analysis
- **Workers**: 8 × c2-standard-60 instances
- **Cost per hour**: $3/instance = $24/hour total
- **Estimated duration**: 20-25 minutes
- **Total cost**: ~$8-10

## Performance Estimates
- **Concurrency**: 10-15 validations per worker = 80-120 total
- **Average time per validation**: 4 seconds (2 tests × 2 seconds)
- **Throughput**: ~20-25 instances/minute
- **Total time**: 500 instances ÷ 25/min = 20 minutes + overhead

## Step-by-Step Execution

### 1. Deploy the Fleet
```bash
cd /Users/luka/src/cc/mcp-the-force-swebench
./scripts/gcp/deploy_validation_fleet.sh
```

This will:
- Create 8 GCP c2-standard-60 instances
- Install Docker and the tester service
- Pre-pull common Docker images
- Generate `worker_config.json`

### 2. Run Validation
```bash
cd runner/src
python run_parallel_validation.py
```

This will:
- Analyze 500 instances
- Show time/cost estimates
- Distribute load across workers
- Run validation with progress updates
- Save results to `parallel_validation_results.json`

### 3. Monitor Progress
The validator shows real-time progress:
```
[125/500] django__django-11099 PASSED (4.2s) on http://35.1.2.3:8080 [Rate: 23.5/s, ETA: 16s]
```

### 4. Handle Failures
- Automatic retry on different workers
- Up to 2 retries per instance
- Detailed error logging

### 5. Destroy Fleet
```bash
./scripts/gcp/deploy_validation_fleet.sh --destroy
```

## Load Distribution Strategy

### Worker 1-2: Django (231 instances)
- Heaviest workload
- Complex framework tests
- Split evenly (115/116)

### Worker 3: SymPy (75 instances)
- Math-heavy computations
- Potentially slower tests

### Worker 4: Matplotlib + Sphinx (78 instances)
- Graphics rendering (34)
- Documentation building (44)

### Worker 5: Scikit-learn (32 instances)
- ML algorithm tests
- Can be compute-intensive

### Worker 6: Mixed repos (63 instances)
- Astropy (22)
- Xarray (22)
- Pytest (19)

### Worker 7: Small repos (28 instances)
- Pylint (10)
- Requests (8)
- Seaborn (2)
- Flask (1)
- Overflow from other workers

### Worker 8: Retry pool
- Handles retries
- Load balancer
- Backup for failures

## Expected Results

Based on our testing:
- **~95%+ validation rate** expected
- Most failures will be edge cases
- Django data-file tests may show warnings
- Some instances may timeout on first try

## Failure Analysis

Common failure patterns:
1. **Timeout**: Complex tests taking >2 minutes
2. **Import errors**: Missing obscure dependencies
3. **Test discovery**: Unusual test structures
4. **Patch conflicts**: Rare patch application issues

## Commands Summary

```bash
# Deploy fleet (one time)
./scripts/gcp/deploy_validation_fleet.sh

# Run validation
cd runner/src
python run_parallel_validation.py

# Check results
cat parallel_validation_results.json | jq '.validation_rate'

# Destroy fleet (important!)
./scripts/gcp/deploy_validation_fleet.sh --destroy
```

## Ready to Execute!

The system is fully prepared for parallel validation. The entire process should complete in under 30 minutes with comprehensive results.