#!/bin/bash
# Deploy/update the tester service on the GCP instance

set -e

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"
TESTER_DIR="/home/luka_crnkovicfriis_king_com/tester"

echo "🚀 Deploying tester service to '$INSTANCE_NAME'..."

# Check if instance is running
STATUS=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(status)" 2>/dev/null || echo "NOT_FOUND")

if [ "$STATUS" != "RUNNING" ]; then
    echo "❌ Instance is not running! Start it first with: ./scripts/gcp/start-instance.sh"
    exit 1
fi

# Get the tester service files
TESTER_PY="${1:-runner/docker/tester/tester_service/tester.py}"
DOCKERFILE="${2:-runner/docker/tester/Dockerfile}"
REQUIREMENTS="${3:-runner/docker/tester/requirements.txt}"

if [ ! -f "$TESTER_PY" ]; then
    echo "❌ Tester service file not found: $TESTER_PY"
    echo "Usage: $0 [tester.py] [Dockerfile] [requirements.txt]"
    exit 1
fi

echo "📦 Copying files to instance..."

# Copy files
gcloud compute scp "$TESTER_PY" \
    "${INSTANCE_NAME}:${TESTER_DIR}/tester_service/tester.py" \
    --zone="$ZONE"

if [ -f "$DOCKERFILE" ]; then
    gcloud compute scp "$DOCKERFILE" \
        "${INSTANCE_NAME}:${TESTER_DIR}/Dockerfile" \
        --zone="$ZONE"
fi

if [ -f "$REQUIREMENTS" ]; then
    gcloud compute scp "$REQUIREMENTS" \
        "${INSTANCE_NAME}:${TESTER_DIR}/requirements.txt" \
        --zone="$ZONE"
fi

echo "🔨 Building and restarting service..."

# Build and restart on the instance
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="
    cd $TESTER_DIR && \
    docker build -t swe-bench-tester . && \
    docker stop swe-bench-tester || true && \
    docker rm swe-bench-tester || true && \
    docker run -d --name swe-bench-tester \
        -p 8080:8080 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --restart unless-stopped \
        swe-bench-tester
"

# Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "✅ Deployment complete!"
echo "🔗 Tester service URL: http://$EXTERNAL_IP:8080/test"
echo ""
echo "Test with: curl -X POST http://$EXTERNAL_IP:8080/test -H 'Content-Type: application/json' -d '{\"instance_id\": \"django__django-11133\", \"patch\": \"\", \"timeout\": 300}'"