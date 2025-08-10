#!/bin/bash
# Update tester service with pytest parsing fix

set -e

echo "Updating tester service with pytest parsing fix..."

# Worker IPs (from worker_config.json)
WORKERS=(
    "35.225.246.28"
    "35.223.155.202"
    "35.222.240.178"
    "35.239.113.60"
    "104.154.225.178"
    "35.239.87.170"
    "35.232.129.144"
    "34.170.78.137"
)

TESTER_FILE="../docker/tester/tester_service/tester.py"

if [ ! -f "$TESTER_FILE" ]; then
    echo "Error: $TESTER_FILE not found"
    exit 1
fi

echo "Deploying fix to ${#WORKERS[@]} workers..."

for i in "${!WORKERS[@]}"; do
    ip="${WORKERS[$i]}"
    echo -e "\n[$((i+1))/${#WORKERS[@]}] Updating worker at $ip..."
    
    # Copy fixed tester.py
    scp -o StrictHostKeyChecking=no "$TESTER_FILE" "ubuntu@$ip:/tmp/tester.py" || {
        echo "  Warning: Failed to copy to $ip"
        continue
    }
    
    # Update the file and restart service
    ssh -o StrictHostKeyChecking=no "ubuntu@$ip" << 'EOF'
        # Backup original
        sudo cp /home/ubuntu/tester/tester_service/tester.py /home/ubuntu/tester/tester_service/tester.py.bak
        
        # Apply fix
        sudo cp /tmp/tester.py /home/ubuntu/tester/tester_service/tester.py
        
        # Restart service
        sudo systemctl restart tester
        
        # Verify it's running
        sleep 2
        if sudo systemctl is-active --quiet tester; then
            echo "  ✓ Service restarted successfully"
        else
            echo "  ✗ Service failed to start"
            sudo journalctl -u tester -n 20
        fi
EOF
    
    if [ $? -ne 0 ]; then
        echo "  Warning: Failed to update $ip"
        continue
    fi
    
    echo "  ✓ Worker $ip updated"
done

echo -e "\n✓ All workers updated with pytest parsing fix"
echo "The fix ensures pytest output parsing correctly identifies the summary line."
