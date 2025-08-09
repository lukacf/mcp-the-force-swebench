# SWE-Bench Evaluator Documentation

## Overview

The SWE-Bench Evaluator is a high-performance system for evaluating code patches against the SWE-Bench dataset. It runs tests in Docker containers on Google Cloud Platform, executing only the specific tests needed for each patch rather than entire test suites.

### Key Features

- ✅ **Fast Evaluation**: Runs only test files specified in `test_patch` (seconds vs minutes)
- ✅ **Universal Docker Execution**: All tests run in pre-built Docker containers on GCP
- ✅ **Auto-dependency Installation**: Automatically installs missing dependencies (pytest, pytz, etc.)
- ✅ **Multi-framework Support**: Works with pytest, Django, and other test frameworks
- ✅ **Simple API**: `evaluate_patch(instance, patch) → {"passed": bool, ...}`

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Evaluator     │────▶│   GCP Tester     │────▶│ Docker Container│
│  (evaluator.py) │ HTTP│  (FastAPI)       │     │ (Epoch AI Image)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                                  │
         │                                                  │
         ▼                                                  ▼
   Extract test files                              Run specific tests
   from test_patch                                 Auto-install deps
```

## Setup Guide

### Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Python 3.11+**
4. **Git**

### Step 1: Create GCP Instance

```bash
# Clone the repository
git clone https://github.com/lukacf/mcp-the-force-swebench.git
cd mcp-the-force-swebench

# Create GCP instance (one-time setup)
./scripts/gcp/create-instance.sh
```

This creates a `c2-standard-60` instance with:
- 60 vCPUs, 240GB RAM
- 500GB SSD
- Docker pre-installed
- ~$3/hour when running

### Step 2: Deploy Tester Service

```bash
# Start the instance
./scripts/gcp/start-instance.sh

# Deploy the tester service
./scripts/gcp/deploy-tester-v2.sh

# Verify it's running
./scripts/gcp/status.sh
```

The tester service will be available at `http://<EXTERNAL_IP>:8080/test`

### Step 3: Install Python Dependencies

```bash
cd runner/src
pip install requests
```

## Usage

### Basic Usage

```python
from evaluator import evaluate_patch
import json

# Load a SWE-Bench instance
with open('swe_bench_instances.jsonl', 'r') as f:
    instance = json.loads(f.readline())

# Evaluate a patch
result = evaluate_patch(instance, your_patch)

# Check if it passed
if result['passed']:
    print("✅ All tests passed!")
else:
    print(f"❌ Tests failed: {result['error']}")
```

### API Reference

#### `evaluate_patch(instance, patch, workdir=None, force_local=False)`

Evaluates a patch against a SWE-Bench instance.

**Parameters:**
- `instance` (dict): SWE-Bench instance with `test_patch` field
- `patch` (str): The code patch to evaluate
- `workdir` (str, optional): Ignored (legacy parameter)
- `force_local` (bool, optional): Ignored (always uses GCP)

**Returns:**
```python
{
    "instance_id": str,
    "passed": bool,
    "error": str or None,
    "test_output": str,
    "test_files": List[str],
    "stats": {
        "passed": int,
        "failed": int,
        "errors": int,
        "duration": float
    }
}
```

#### `extract_test_files_from_patch(test_patch, workdir=None)`

Extracts test file paths from a test_patch diff.

**Parameters:**
- `test_patch` (str): The test patch diff
- `workdir` (str, optional): Working directory (for data file resolution)

**Returns:**
- List[str]: Test file paths to run

### Example: Testing Multiple Patches

```python
import json
from evaluator import evaluate_patch

# Load instances
instances = []
with open('swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        instances.append(json.loads(line))

# Test each with correct patch
for instance in instances[:5]:
    print(f"\nTesting {instance['instance_id']}...")
    result = evaluate_patch(instance, instance['patch'])
    print(f"Result: {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Time: {result['stats']['duration']}s")
```

### Example: Custom Patch Testing

```python
# Test a custom patch
my_patch = '''
diff --git a/src/module.py b/src/module.py
--- a/src/module.py
+++ b/src/module.py
@@ -10,7 +10,7 @@ def function():
-    return old_value
+    return new_value
'''

result = evaluate_patch(instance, my_patch)
```

## How It Works

1. **Test Extraction**: The evaluator parses `test_patch` to identify which test files to run
2. **GCP Request**: Sends instance_id, patch, and test_files to the GCP tester
3. **Docker Execution**: 
   - Pulls the pre-built Docker image for the instance
   - Applies the patch
   - Auto-installs missing dependencies
   - Runs only the specific test files
4. **Result Parsing**: Returns pass/fail status with detailed output

## Cost Management

The GCP instance costs ~$3/hour. Always remember to:

```bash
# Stop when not in use
./scripts/gcp/stop-instance.sh

# Check status
./scripts/gcp/status.sh

# Start when needed
./scripts/gcp/start-instance.sh
```

## Supported Repositories

All 12 SWE-Bench repositories are supported:

| Repository | Test Framework | Status |
|------------|----------------|---------|
| astropy/astropy | pytest | ✅ Working |
| django/django | Django runtests.py | ✅ Working |
| matplotlib/matplotlib | pytest | ✅ Working |
| mwaskom/seaborn | pytest | ✅ Working |
| pallets/flask | pytest | ✅ Working |
| psf/requests | pytest | ✅ Working |
| pydata/xarray | pytest | ✅ Working |
| pylint-dev/pylint | pytest | ✅ Working |
| pytest-dev/pytest | pytest | ✅ Working |
| scikit-learn/scikit-learn | pytest | ✅ Working |
| sphinx-doc/sphinx | pytest | ✅ Working |
| sympy/sympy | pytest | ✅ Working |

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if GCP instance is running: `./scripts/gcp/status.sh`
   - Verify tester service is up: `curl http://<IP>:8080/docs`

2. **Patch Failed to Apply**
   - Ensure patch format is correct (unified diff format)
   - Check that patch applies to the base commit

3. **Tests Not Found**
   - Verify test_patch contains actual test modifications
   - Check that test files exist in the repository

4. **Timeout Errors**
   - Default timeout is 900s (15 minutes)
   - Some complex tests may need longer

### Logs and Debugging

Check GCP tester logs:
```bash
gcloud compute ssh swe-bench-beast --zone=us-central1-a \
  --command="docker logs swe-bench-tester --tail 50"
```

Check evaluator behavior:
```python
import logging
logging.basicConfig(level=logging.INFO)
# Now evaluate_patch will show detailed logs
```

### Manual Testing

Test the GCP service directly:
```bash
curl -X POST http://<IP>:8080/test \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "pallets__flask-5014",
    "patch": "",
    "timeout": 60,
    "test_files": ["tests/test_blueprints.py"]
  }'
```

## Advanced Usage

### Batch Evaluation

```python
from evaluator import evaluate_patch
import concurrent.futures
import json

def evaluate_instance(instance):
    try:
        result = evaluate_patch(instance, instance['patch'])
        return {
            'instance_id': instance['instance_id'],
            'passed': result['passed'],
            'duration': result['stats']['duration']
        }
    except Exception as e:
        return {
            'instance_id': instance['instance_id'],
            'error': str(e)
        }

# Load instances
instances = []
with open('swe_bench_instances.jsonl', 'r') as f:
    for line in f:
        instances.append(json.loads(line))

# Parallel evaluation (be nice to the server)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(evaluate_instance, instances[:10]))

# Summary
passed = sum(1 for r in results if r.get('passed', False))
print(f"Passed: {passed}/{len(results)}")
```

### Integration with SWE-Bench

```python
# Use with official SWE-Bench evaluation
from evaluator import evaluate_patch

def swebench_evaluation_function(instance, patch):
    """Compatible with SWE-Bench evaluation scripts."""
    result = evaluate_patch(instance, patch)
    return {
        'instance_id': instance['instance_id'],
        'test_result': 'PASSED' if result['passed'] else 'FAILED',
        'test_output': result['test_output']
    }
```

## Performance

Typical evaluation times:
- Simple patches: 2-5 seconds
- Complex patches: 5-10 seconds  
- Full test suite (comparison): 30-300 seconds

The evaluator is 10-100x faster than running full test suites because it only runs the specific tests defined in `test_patch`.

## Contributing

When modifying the evaluator:

1. Test locally first
2. Commit changes: `git add -A && git commit -m "Description"`
3. Push to GitHub: `git push origin main`
4. Deploy to GCP: `./scripts/gcp/deploy-tester-v2.sh`

## Architecture Details

### Evaluator (`evaluator.py`)
- Extracts test files from test_patch
- Sends requests to GCP tester
- Handles response parsing

### GCP Tester (`tester_service/tester.py`)
- FastAPI service running on GCP
- Manages Docker containers
- Auto-installs dependencies
- Runs specific test files

### Docker Images
- Pre-built by Epoch AI for SWE-Bench
- Contains repository at correct commit
- Includes base dependencies
- Missing deps installed at runtime

---

For more information, see the [main project README](../README.md).