#!/bin/bash
# Deploy the updated tester v2 to GCP

set -e

echo "Deploying tester v2 to GCP..."

# Get the GCP instance IP
INSTANCE_IP="35.209.45.223"

# Copy the new tester file
echo "Copying tester_v2.py to GCP instance..."
scp tester_service/tester_v2.py swe-bench@${INSTANCE_IP}:~/tester/tester_service/

# SSH to the instance and restart the service
echo "Restarting tester service..."
ssh swe-bench@${INSTANCE_IP} << 'EOF'
cd ~/tester
# Backup current tester
cp tester_service/tester.py tester_service/tester_backup.py
# Replace with v2
cp tester_service/tester_v2.py tester_service/tester.py
# Restart the service
sudo supervisorctl restart tester
# Check status
sleep 2
sudo supervisorctl status tester
EOF

echo "Testing the updated service..."
curl -s http://${INSTANCE_IP}:8080/health | jq .

echo "Deployment complete!"