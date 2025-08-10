#!/bin/bash
# Update all GCP workers with the fixed tester service

set -e

# Load worker URLs
WORKER_IPS=($(cat worker_config.json | grep http | cut -d'"' -f2 | cut -d'/' -f3 | cut -d':' -f1))

echo "Updating ${#WORKER_IPS[@]} workers with fixed tester service..."
echo "======================================================"

# Build the Docker image locally first for linux/amd64 platform
echo "Building fixed tester image for linux/amd64..."
cd /Users/luka/src/cc/mcp-the-force-swebench/runner/docker/tester
docker buildx build --platform linux/amd64 -t swe-bench-tester:fixed .

# Save the image to a tar file
echo "Saving image to tar file..."
docker save swe-bench-tester:fixed -o tester-fixed.tar

# Update each worker
for i in "${!WORKER_IPS[@]}"; do
    IP="${WORKER_IPS[$i]}"
    echo ""
    echo "Updating worker $((i+1)): $IP"
    echo "-----------------------------------"
    
    # Copy the image to the worker
    echo "  Copying image..."
    gcloud compute scp tester-fixed.tar swe-bench-worker-$((i+1)):/tmp/tester-fixed.tar --zone=us-central1-a
    
    # Load and restart the service on the worker
    echo "  Loading image and restarting service..."
    gcloud compute ssh swe-bench-worker-$((i+1)) --zone=us-central1-a --command="
        sudo docker load -i /tmp/tester-fixed.tar && \
        sudo docker stop swe-bench-tester || true && \
        sudo docker rm swe-bench-tester || true && \
        sudo docker run -d --name swe-bench-tester \
            -p 8080:8080 \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v /mnt/disks/ssd/repos:/scratch/repos \
            swe-bench-tester:fixed && \
        rm /tmp/tester-fixed.tar && \
        echo 'Worker updated successfully'
    "
    
    # Test the worker
    echo "  Testing worker..."
    sleep 5
    curl -s http://$IP:8080/health | grep -q healthy && echo "  ✓ Worker is healthy" || echo "  ✗ Worker health check failed"
done

echo ""
echo "All workers updated!"
echo "======================================================"

# Clean up local tar file
rm -f tester-fixed.tar