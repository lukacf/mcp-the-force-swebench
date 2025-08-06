#!/bin/bash
# Check status of the SWE-Bench tester instance

set -e

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"

echo "📊 Checking status of '$INSTANCE_NAME'..."
echo ""

# Get instance details
STATUS=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(status)" 2>/dev/null || echo "NOT_FOUND")

if [ "$STATUS" = "NOT_FOUND" ]; then
    echo "❌ Instance not found!"
    exit 1
fi

# Get more details
MACHINE_TYPE=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(machineType.scope(machineTypes))")

DISK_SIZE=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(disks[0].diskSizeGb)")

echo "Instance: $INSTANCE_NAME"
echo "Zone: $ZONE"
echo "Status: $STATUS"
echo "Machine Type: $MACHINE_TYPE"
echo "Disk Size: ${DISK_SIZE}GB"

if [ "$STATUS" = "RUNNING" ]; then
    EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
        --zone="$ZONE" \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    echo "External IP: $EXTERNAL_IP"
    echo ""
    echo "🔗 Tester service URL: http://$EXTERNAL_IP:8080/test"
    
    # Estimate hourly cost (rough approximation)
    echo ""
    echo "💸 Estimated hourly cost: ~\$3.00/hour (c2-standard-60)"
    echo "💸 Estimated daily cost: ~\$72/day if running 24/7"
    echo ""
    echo "⚠️  Don't forget to stop it when not in use!"
else
    echo ""
    echo "💤 Instance is stopped - not incurring compute charges"
fi