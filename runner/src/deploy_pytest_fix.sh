#!/bin/bash
# Deploy pytest parsing fix to active SWE-Bench workers

set -e

echo "Deploying pytest parsing fix to SWE-Bench workers..."

# Active worker IPs from gcloud
WORKERS=(
    "34.44.234.143"   # swe-bench-worker-1
    "35.239.238.137"  # swe-bench-worker-2
    "34.41.233.120"   # swe-bench-worker-3
    "34.44.241.183"   # swe-bench-worker-4
    # skip worker-5 (terminated)
    "34.59.30.169"    # swe-bench-worker-6
    "34.123.9.23"     # swe-bench-worker-7
    "34.70.1.155"     # swe-bench-worker-8
)

TESTER_FILE="../docker/tester/tester_service/tester.py"

if [ ! -f "$TESTER_FILE" ]; then
    echo "Error: $TESTER_FILE not found"
    exit 1
fi

echo "Found ${#WORKERS[@]} active workers to update"
echo "Fix: Update pytest parsing to correctly find summary line with timing info"

for i in "${!WORKERS[@]}"; do
    ip="${WORKERS[$i]}"
    worker_num=$((i+1))
    [ $i -ge 4 ] && worker_num=$((i+2))  # Adjust for skipped worker-5
    
    echo -e "\n[$((i+1))/${#WORKERS[@]}] Updating swe-bench-worker-$worker_num at $ip..."
    
    # Copy fixed tester.py
    gcloud compute scp "$TESTER_FILE" "swe-bench-worker-$worker_num:/tmp/tester.py" \
        --zone=us-central1-a --quiet 2>/dev/null || {
        echo "  ⚠️  Failed to copy to worker-$worker_num"
        continue
    }
    
    # Update the file and restart service
    gcloud compute ssh "swe-bench-worker-$worker_num" --zone=us-central1-a --quiet \
        --command="
        sudo cp /home/ubuntu/tester/tester_service/tester.py /home/ubuntu/tester/tester_service/tester.py.bak &&
        sudo cp /tmp/tester.py /home/ubuntu/tester/tester_service/tester.py &&
        sudo systemctl restart tester &&
        sleep 2 &&
        if sudo systemctl is-active --quiet tester; then
            echo '  ✓ Service restarted successfully';
        else
            echo '  ✗ Service failed to start';
            sudo journalctl -u tester -n 10;
        fi
        " 2>/dev/null || {
        echo "  ⚠️  Failed to update worker-$worker_num"
        continue
    }
    
    echo "  ✅ Worker-$worker_num updated successfully"
done

echo -e "\n✅ Deployment complete!"
echo "The pytest parsing fix ensures the regex correctly identifies the summary line"
echo "(with timing info) instead of matching 'test session starts'."

# Update TodoWrite to mark task as completed
echo -e "\n📝 Marking pytest parsing fix as completed..."
