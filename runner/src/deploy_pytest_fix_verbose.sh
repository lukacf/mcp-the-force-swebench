#!/bin/bash
# Deploy pytest parsing fix to active SWE-Bench workers

set -e

echo "Deploying pytest parsing fix to SWE-Bench workers..."

# Test on worker-1 first
echo "Testing deployment on swe-bench-worker-1..."

TESTER_FILE="../docker/tester/tester_service/tester.py"

if [ ! -f "$TESTER_FILE" ]; then
    echo "Error: $TESTER_FILE not found"
    exit 1
fi

echo "Copying tester.py to worker-1..."
gcloud compute scp "$TESTER_FILE" "swe-bench-worker-1:/tmp/tester.py" --zone=us-central1-a

echo "Applying fix on worker-1..."
gcloud compute ssh swe-bench-worker-1 --zone=us-central1-a --command="
    echo 'Backing up original file...' &&
    sudo cp /home/ubuntu/tester/tester_service/tester.py /home/ubuntu/tester/tester_service/tester.py.bak &&
    echo 'Applying fixed version...' &&
    sudo cp /tmp/tester.py /home/ubuntu/tester/tester_service/tester.py &&
    echo 'Restarting tester service...' &&
    sudo systemctl restart tester &&
    sleep 2 &&
    echo 'Checking service status...' &&
    if sudo systemctl is-active --quiet tester; then
        echo '✓ Service is running';
        curl -s http://localhost:8000/health || echo 'Warning: Health check failed';
    else
        echo '✗ Service failed to start';
        sudo journalctl -u tester -n 20;
    fi
"

echo -e "\nIf successful, we'll deploy to all workers..."
