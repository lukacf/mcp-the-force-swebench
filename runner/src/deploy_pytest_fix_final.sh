#!/bin/bash
# Deploy pytest parsing fix to all SWE-Bench workers

set -e

echo "🚀 Deploying pytest parsing fix to SWE-Bench workers..."

# Active workers from gcloud
WORKERS=(1 2 3 4 6 7 8)  # Skip worker-5 (terminated)

TESTER_FILE="../docker/tester/tester_service/tester.py"
REMOTE_PATH="/home/mcp-the-force-swebench/runner/docker/tester/tester_service/tester.py"

if [ ! -f "$TESTER_FILE" ]; then
    echo "Error: $TESTER_FILE not found"
    exit 1
fi

echo "Found ${#WORKERS[@]} workers to update"
echo "Fix: Correct pytest output parsing to find summary line with timing info"
echo ""

success_count=0

for worker in "${WORKERS[@]}"; do
    echo "[$worker/${#WORKERS[@]}] Updating swe-bench-worker-$worker..."
    
    # Copy fixed tester.py
    if gcloud compute scp "$TESTER_FILE" "swe-bench-worker-$worker:/tmp/tester.py" --zone=us-central1-a --quiet; then
        echo "  ✓ File copied"
    else
        echo "  ✗ Failed to copy file"
        continue
    fi
    
    # Apply fix and restart service
    if gcloud compute ssh "swe-bench-worker-$worker" --zone=us-central1-a --command="
        sudo cp '$REMOTE_PATH' '${REMOTE_PATH}.bak' &&
        sudo cp /tmp/tester.py '$REMOTE_PATH' &&
        sudo systemctl restart tester &&
        sleep 2 &&
        if sudo systemctl is-active --quiet tester; then
            echo '  ✓ Service restarted successfully';
            curl -s http://localhost:8000/health | grep -q healthy && echo '  ✓ Health check passed' || echo '  ⚠️  Health check failed';
        else
            echo '  ✗ Service failed to start';
            exit 1;
        fi
    " 2>/dev/null; then
        echo "  ✅ Worker-$worker updated successfully"
        ((success_count++))
    else
        echo "  ✗ Failed to update worker-$worker"
    fi
    echo ""
done

echo "✨ Deployment complete! Updated $success_count/${#WORKERS[@]} workers"
echo ""
echo "The fix changes the pytest parsing regex from:"
echo "  re.search() - which returns the FIRST match ('test session starts')"
echo "To:"
echo "  re.finditer() - to find the match containing timing info"
echo ""
echo "This ensures we correctly parse test results from the summary line."
