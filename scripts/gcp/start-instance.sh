#!/bin/bash
# Start the SWE-Bench tester instance

set -e

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"

echo "🚀 Starting instance '$INSTANCE_NAME' in zone '$ZONE'..."

# Start the instance
gcloud compute instances start "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --quiet

echo "⏳ Waiting for instance to be ready..."
sleep 10

# Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo "✅ Instance started successfully!"
echo "🌐 External IP: $EXTERNAL_IP"
echo "🔗 Tester service URL: http://$EXTERNAL_IP:8080/test"
echo ""
echo "⚠️  Remember to stop it when done: ./scripts/gcp/stop-instance.sh"