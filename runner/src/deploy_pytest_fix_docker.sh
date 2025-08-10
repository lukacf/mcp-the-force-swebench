#!/bin/bash
# Deploy pytest parsing fix to Docker-based tester services

set -e

echo "🐳 Deploying pytest parsing fix to SWE-Bench workers (Docker version)..."

# Active workers
WORKERS=(1 2 3 4 6 7 8)

TESTER_FILE="../docker/tester/tester_service/tester.py"

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
    
    # Copy fixed tester.py to worker
    if gcloud compute scp "$TESTER_FILE" "swe-bench-worker-$worker:/tmp/tester.py" --zone=us-central1-a --quiet; then
        echo "  ✓ File copied"
    else
        echo "  ✗ Failed to copy file"
        continue
    fi
    
    # Update file in Docker container and restart
    if gcloud compute ssh "swe-bench-worker-$worker" --zone=us-central1-a --command="
        # Copy file into running container
        sudo docker cp /tmp/tester.py swe-bench-tester:/app/tester_service/tester.py &&
        echo '  ✓ File updated in container' &&
        
        # Restart the container to apply changes
        sudo docker restart swe-bench-tester &&
        echo '  ✓ Container restarting...' &&
        
        # Wait for service to come up
        sleep 5 &&
        
        # Check if service is healthy
        if curl -s http://localhost:8080/health | grep -q healthy; then
            echo '  ✓ Health check passed';
        else
            echo '  ⚠️  Health check failed';
            sudo docker logs swe-bench-tester --tail 20;
            exit 1;
        fi
    " 2>&1; then
        echo "  ✅ Worker-$worker updated successfully"
        ((success_count++))
    else
        echo "  ✗ Failed to update worker-$worker"
    fi
    echo ""
done

echo "✨ Deployment complete! Updated $success_count/${#WORKERS[@]} workers"

if [ $success_count -gt 0 ]; then
    echo ""
    echo "🎯 The pytest parsing fix is now deployed!"
    echo "Key changes:"
    echo "  - Fixed regex to iterate through all matches instead of just the first"
    echo "  - Now correctly identifies the summary line containing timing info"
    echo "  - Resolves the issue where 'test session starts' was being parsed instead"
fi
