# SWE-Bench Evaluator Quick Start

Get up and running in 5 minutes!

## Prerequisites
- Google Cloud account with billing
- `gcloud` CLI installed
- Python 3.11+

## 1. Clone and Setup (30 seconds)

```bash
git clone https://github.com/lukacf/mcp-the-force-swebench.git
cd mcp-the-force-swebench
```

## 2. Start GCP Infrastructure (2 minutes)

```bash
# Create instance (first time only)
./scripts/gcp/create-instance.sh

# Start the instance
./scripts/gcp/start-instance.sh

# Deploy tester service
./scripts/gcp/deploy-tester-v2.sh
```

## 3. Test Your First Patch (30 seconds)

```python
# cd runner/src
# python

from evaluator import evaluate_patch
import json

# Load a test instance
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

# Test with the correct patch
result = evaluate_patch(instance, instance['patch'])
print(f"Passed: {result['passed']}")
print(f"Time: {result['stats']['duration']}s")
```

## 4. Stop Instance (Save Money!)

```bash
./scripts/gcp/stop-instance.sh
```

## That's It! 🎉

You've just evaluated a SWE-Bench patch in seconds instead of minutes.

### Next Steps

- Read the [full documentation](EVALUATOR_DOCS.md)
- Try evaluating your own patches
- Run systematic tests on multiple instances

### Quick Tips

- **Check status**: `./scripts/gcp/status.sh`
- **View logs**: `gcloud compute ssh swe-bench-beast --zone=us-central1-a --command="docker logs swe-bench-tester --tail 20"`
- **Test specific repos**: The evaluator works with all 12 SWE-Bench repositories

### Cost: ~$3/hour when running, so always stop when done!