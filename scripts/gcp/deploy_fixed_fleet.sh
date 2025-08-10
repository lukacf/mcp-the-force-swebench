#!/bin/bash
# Deploy a new fleet with the fixed tester image (no local build needed)

set -e

# Configuration
NUM_WORKERS=${NUM_WORKERS:-8}
INSTANCE_TYPE="c2-standard-60"
ZONE="us-central1-a"
PROJECT=$(gcloud config get-value project)
DISK_SIZE="500GB"
DISK_TYPE="pd-ssd"
FIXED_IMAGE="us-central1-docker.pkg.dev/king-ai-gpts-luka-dev/swebench/swe-bench-tester:v2-fixed"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 SWE-Bench Fixed Fleet Deployment${NC}"
echo "=================================="
echo "Workers: $NUM_WORKERS"
echo "Instance type: $INSTANCE_TYPE"
echo "Zone: $ZONE"
echo "Project: $PROJECT"
echo "Fixed image: $FIXED_IMAGE"
echo ""

# Create startup script that uses the fixed image
cat > /tmp/worker-startup-fixed.sh << EOF
#!/bin/bash
set -euo pipefail

exec >> /var/log/startup-fixed.log 2>&1
echo "=== \$(date -Is) START fixed tester deployment ==="

# Install Docker
if ! command -v docker >/dev/null 2>&1; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Wait for Docker daemon
echo "Waiting for Docker daemon..."
for i in {1..60}; do
    if systemctl is-active --quiet docker || docker info >/dev/null 2>&1; then
        echo "Docker ready."
        break
    fi
    sleep 2
done

# Create scratch directory
mkdir -p /mnt/disks/ssd/repos

# Pull the fixed image
IMAGE="$FIXED_IMAGE"
echo "Pulling fixed image: \$IMAGE"
docker pull "\$IMAGE"

# Run the fixed tester
echo "Starting fixed tester container"
docker run -d --name swe-bench-tester \\
    -p 8080:8080 \\
    -v /var/run/docker.sock:/var/run/docker.sock \\
    -v /mnt/disks/ssd/repos:/scratch/repos \\
    --restart unless-stopped \\
    -e TESTER_VERSION=v2-fixed \\
    "\$IMAGE"

# Pre-pull some common images
echo "Pre-pulling common SWE-bench images..."
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-10097:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.pallets__flask-5014:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.sympy__sympy-13895:latest &

echo "=== \$(date -Is) END fixed tester deployment ==="
echo "Worker ready with fixed tester!"
EOF

# Create instances
echo -e "${YELLOW}Creating $NUM_WORKERS worker instances with fixed tester...${NC}"
WORKER_IPS=()

for i in $(seq 1 $NUM_WORKERS); do
    instance_name="swe-bench-worker-$i"
    echo -e "\n${GREEN}Creating $instance_name...${NC}"
    
    # Create instance
    gcloud compute instances create $instance_name \
        --zone=$ZONE \
        --machine-type=$INSTANCE_TYPE \
        --boot-disk-size=$DISK_SIZE \
        --boot-disk-type=$DISK_TYPE \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --metadata-from-file startup-script=/tmp/worker-startup-fixed.sh \
        --tags=swe-bench-worker \
        --preemptible
    
    # Get IP
    IP=$(gcloud compute instances describe $instance_name --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    WORKER_IPS+=($IP)
    echo "Worker $i IP: $IP"
done

# Ensure firewall rule exists
if ! gcloud compute firewall-rules describe allow-swe-bench-tester &>/dev/null; then
    echo -e "\n${YELLOW}Creating firewall rule...${NC}"
    gcloud compute firewall-rules create allow-swe-bench-tester \
        --allow tcp:8080 \
        --source-ranges 0.0.0.0/0 \
        --target-tags swe-bench-worker
fi

# Wait for workers to be ready
echo -e "\n${YELLOW}Waiting for fixed workers to be ready...${NC}"
READY_COUNT=0
MAX_WAIT=300  # 5 minutes max wait per worker

for i in $(seq 1 $NUM_WORKERS); do
    IP=${WORKER_IPS[$i-1]}
    echo -n "Worker $i ($IP): "
    
    SUCCESS=false
    for attempt in $(seq 1 $MAX_WAIT); do
        if curl -sf "http://$IP:8080/health" &>/dev/null; then
            echo -e "${GREEN}Ready!${NC}"
            ((READY_COUNT++))
            SUCCESS=true
            break
        fi
        echo -n "."
        sleep 1
    done
    
    if [ "$SUCCESS" = false ]; then
        echo -e " ${RED}Timed out${NC}"
    fi
done

# Generate worker configuration
echo -e "\n${YELLOW}Generating worker configuration...${NC}"
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
    "tester_version": "v2-fixed",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo -e "${GREEN}✅ Worker configuration saved to worker_config.json${NC}"

# Cleanup
rm -f /tmp/worker-startup-fixed.sh

# Summary
echo ""
echo -e "${GREEN}=================================="
echo "🎉 Fixed Fleet Ready!"
echo "=================================="
echo "Ready workers: $READY_COUNT/$NUM_WORKERS"
if [ $READY_COUNT -ge 5 ]; then
    echo -e "${GREEN}✅ Enough workers ready for validation!${NC}"
else
    echo -e "${YELLOW}⚠️  Only $READY_COUNT workers ready. You may want to wait longer.${NC}"
fi
echo ""
echo "Fixed tester includes:"
echo "  - python -m pytest (correct interpreter)"
echo "  - No --no-header flag"
echo "  - Increased timeouts (420s/300s)" 
echo "  - Python version verification"
echo ""
echo "To run validation:"
echo "  cd runner/src"
echo "  python parallel_validator.py"
echo "=================================="
echo -e "${NC}"