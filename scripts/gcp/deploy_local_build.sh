#!/bin/bash
# Deploy workers that build tester locally (SIMPLE - no registry complexity)
# Lesson learned: Don't overcomplicate things. Local builds worked before.

set -e

NUM_WORKERS=${NUM_WORKERS:-3}
INSTANCE_TYPE="c2-standard-60"
ZONE="us-central1-a"
PROJECT=$(gcloud config get-value project)

echo "🚀 Deploying $NUM_WORKERS workers with LOCAL BUILD (no registry needed)"
echo "Goal: Get testing framework working on 100% of the 499 instances"

# Create startup script that builds locally (like we did before)
cat > /tmp/worker-startup-local.sh << 'EOF'
#!/bin/bash
set -euo pipefail

exec >> /var/log/startup-local.log 2>&1
echo "=== $(date -Is) START local build deployment ==="

# Install Docker if not present
if ! command -v docker >/dev/null 2>&1; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Wait for Docker daemon to be ready
echo "Waiting for Docker daemon..."
for i in {1..120}; do
    if systemctl is-active --quiet docker || docker info >/dev/null 2>&1; then
        echo "Docker ready"
        break
    fi
    sleep 2
done

# Install git
echo "Installing git..."
apt-get update && apt-get install -y git

# Create scratch directory
mkdir -p /mnt/disks/ssd/repos

# Clone repo and build tester locally (the simple way that worked)
echo "Cloning repo..."
mkdir -p /opt
cd /opt
rm -rf mcp-the-force-swebench || true
git clone --depth=1 https://github.com/lukacf/mcp-the-force-swebench.git
cd mcp-the-force-swebench/runner/docker/tester

# Build tester with our Python fixes locally
echo "Building tester locally with fixes..."
docker build -t swe-bench-tester:v2-fixed .

# Stop any existing container
echo "Stopping old container..."
docker rm -f swe-bench-tester >/dev/null 2>&1 || true

# Run the locally built tester with infrastructure fixes
echo "Starting fixed tester container with multi-process and health checks..."
docker run -d --name swe-bench-tester \
    -p 8080:8080 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /mnt/disks/ssd/repos:/scratch/repos \
    --restart unless-stopped \
    --ulimit nofile=65535:65535 \
    -e TESTER_VERSION=v2-infra-fixed \
    swe-bench-tester:v2-fixed

# Add Docker cleanup cron job
echo "Setting up Docker cleanup cron job..."
cat > /etc/cron.d/docker-cleanup << 'CRON_EOF'
# Clean up Docker when disk usage is high
*/10 * * * * root if [ $(df -h /var/lib/docker | awk 'NR==2 {print int($5)}') -gt 80 ]; then docker system prune -af --volumes > /var/log/docker-cleanup.log 2>&1; fi
CRON_EOF

# Increase system limits
echo "Configuring system limits..."
sysctl -w net.core.somaxconn=4096 || true
sysctl -w net.ipv4.ip_local_port_range="1024 65000" || true

echo "=== $(date -Is) END local build deployment ==="
echo "Worker ready with infrastructure-hardened tester!"
echo "Features: multi-process API, health checks, Docker cleanup, increased limits"
EOF

# Create workers (use non-preemptible to avoid churn during this critical run)
echo "Creating $NUM_WORKERS worker instances..."
WORKER_IPS=()

for i in $(seq 1 $NUM_WORKERS); do
    instance_name="swe-bench-worker-$i"
    echo "Creating $instance_name..."
    
    # Create instance with local build startup script
    gcloud compute instances create $instance_name \
        --zone=$ZONE \
        --machine-type=$INSTANCE_TYPE \
        --boot-disk-size=500GB \
        --boot-disk-type=pd-ssd \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --metadata-from-file startup-script=/tmp/worker-startup-local.sh \
        --tags=swe-bench-worker \
    
    # Get IP
    IP=$(gcloud compute instances describe $instance_name --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    WORKER_IPS+=($IP)
    echo "Worker $i IP: $IP"
done

# Ensure firewall rule exists
if ! gcloud compute firewall-rules describe allow-swe-bench-tester &>/dev/null; then
    echo "Creating firewall rule..."
    gcloud compute firewall-rules create allow-swe-bench-tester \
        --allow tcp:8080 \
        --source-ranges 0.0.0.0/0 \
        --target-tags swe-bench-worker
fi

# Wait for workers to build and be ready
echo "Waiting for workers to build locally and start (may take 3-5 minutes)..."
READY_COUNT=0
MAX_WAIT=400  # 6+ minutes for build + startup

for i in $(seq 1 $NUM_WORKERS); do
    IP=${WORKER_IPS[$i-1]}
    echo -n "Worker $i ($IP): "
    
    SUCCESS=false
    for attempt in $(seq 1 $MAX_WAIT); do
        if curl -sf "http://$IP:8080/health" &>/dev/null; then
            echo " Ready!"
            ((READY_COUNT++))
            SUCCESS=true
            break
        fi
        echo -n "."
        sleep 1
    done
    
    if [ "$SUCCESS" = false ]; then
        echo " Timed out (check serial console logs)"
    fi
done

# Generate worker configuration
echo "Generating worker configuration..."
cd /Users/luka/src/cc/mcp-the-force-swebench/runner/src
cat > worker_config.json << EOF
{
    "worker_urls": [
EOF

for i in $(seq 1 $NUM_WORKERS); do
    IP=${WORKER_IPS[$i-1]}
    if [ $i -eq $NUM_WORKERS ]; then
        echo "        \"http://$IP:8080\"" >> worker_config.json
    else
        echo "        \"http://$IP:8080\"," >> worker_config.json
    fi
done

cat >> worker_config.json << EOF
    ],
    "num_workers": $NUM_WORKERS,
    "tester_version": "v2-fixed-local",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "✅ Worker configuration saved to worker_config.json"

# Cleanup
rm -f /tmp/worker-startup-local.sh

# Summary
echo ""
echo "=================================="
echo "🎉 Local Build Fleet Ready!"
echo "=================================="
echo "Ready workers: $READY_COUNT/$NUM_WORKERS"
if [ $READY_COUNT -ge 2 ]; then
    echo "✅ Enough workers ready for validation!"
else
    echo "⚠️  Only $READY_COUNT workers ready. Check serial logs if needed."
fi
echo ""
echo "Built locally with fixes:"
echo "  - python -m pytest (correct Python interpreter)"
echo "  - No --no-header flag"  
echo "  - Increased timeouts (420s/300s)"
echo "  - Python version verification"
echo "Infrastructure hardening (GPT-5 recommendations):"
echo "  - Multi-process uvicorn (4 workers)"
echo "  - Health check endpoints (/health, /ready, /live)"
echo "  - Per-worker concurrency limits (3 concurrent)"
echo "  - Backpressure (429 when busy)"
echo "  - Docker image cleanup after tests"
echo "  - Automatic Docker pruning when disk >80%"
echo "  - Increased ulimits and connection backlogs"
echo ""
echo "To run validation:"
echo "  cd runner/src"
echo "  python parallel_validator.py"
echo ""
echo "LESSON LEARNED: Keep it simple. Local builds work."
echo "Goal: Test framework working on 100% of 499 instances."
echo "=================================="