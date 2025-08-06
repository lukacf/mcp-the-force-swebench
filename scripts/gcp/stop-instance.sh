#!/bin/bash
# Stop the SWE-Bench tester instance to save costs

set -e

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"

echo "🛑 Stopping instance '$INSTANCE_NAME' in zone '$ZONE'..."

# Stop the instance
gcloud compute instances stop "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --quiet

echo "✅ Instance stopped successfully!"
echo "💰 You're no longer being charged for the c2-standard-60 instance!"
echo ""
echo "To start it again, run: ./scripts/gcp/start-instance.sh"