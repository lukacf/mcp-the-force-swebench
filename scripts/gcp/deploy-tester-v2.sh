#!/bin/bash
# Deploy the tester service from Git repository

set -e

INSTANCE_NAME="swe-bench-beast"
ZONE="us-central1-a"
REPO_URL="https://github.com/yourusername/mcp-the-force-benchmarks.git"  # TODO: Update this
BRANCH="${BRANCH:-main}"

echo "🚀 Deploying tester service from Git repository..."

# Check if instance is running
STATUS=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(status)" 2>/dev/null || echo "NOT_FOUND")

if [ "$STATUS" != "RUNNING" ]; then
    echo "❌ Instance is not running! Start it first with: ./scripts/gcp/start-instance.sh"
    exit 1
fi

echo "📦 Deploying from branch: $BRANCH"

# Deploy on the instance
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="
    # Clone or update repository
    if [ -d ~/mcp-the-force-benchmarks ]; then
        echo '📥 Updating existing repository...'
        cd ~/mcp-the-force-benchmarks
        git fetch origin
        git checkout $BRANCH
        git pull origin $BRANCH
    else
        echo '📥 Cloning repository...'
        cd ~
        git clone $REPO_URL
        cd mcp-the-force-benchmarks
        git checkout $BRANCH
    fi
    
    # Build and deploy tester service
    echo '🔨 Building Docker image...'
    cd runner/docker/tester
    docker build -t swe-bench-tester .
    
    # Stop and remove old container
    echo '🔄 Restarting service...'
    docker stop swe-bench-tester 2>/dev/null || true
    docker rm swe-bench-tester 2>/dev/null || true
    
    # Start new container
    docker run -d --name swe-bench-tester \
        -p 8080:8080 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --restart unless-stopped \
        swe-bench-tester
    
    # Check if running
    sleep 2
    docker ps | grep swe-bench-tester
"

# Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "✅ Deployment complete!"
echo "🔗 Tester service URL: http://$EXTERNAL_IP:8080/test"
echo ""
echo "📝 To deploy a different branch: BRANCH=feature-xyz ./scripts/gcp/deploy-tester-v2.sh"