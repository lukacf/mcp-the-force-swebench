#!/bin/bash
# SSH into the SWE-Bench tester instance

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"

echo "🔐 Connecting to '$INSTANCE_NAME'..."

gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE"