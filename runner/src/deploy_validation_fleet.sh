#!/bin/bash
#
# Deploy SWE-Bench validation fleet on GCP
# This script creates and configures multiple GCP instances for parallel validation
#

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
ZONE="${GCP_ZONE:-us-central1-a}"
MACHINE_TYPE="${MACHINE_TYPE:-c2-standard-60}"
NUM_WORKERS="${NUM_WORKERS:-8}"
DOCKER_IMAGE="${DOCKER_IMAGE:-swe-bench-tester:latest}"
BOOT_DISK_SIZE="${BOOT_DISK_SIZE:-100GB}"
NETWORK_TAG="swe-bench-worker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== SWE-Bench Validation Fleet Deployment ===${NC}"
echo "Project: $PROJECT_ID"
echo "Zone: $ZONE"
echo "Machine Type: $MACHINE_TYPE"
echo "Number of Workers: $NUM_WORKERS"
echo "Docker Image: $DOCKER_IMAGE"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    exit 1
fi

# Set project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project "$PROJECT_ID"

# Create firewall rule if it doesn't exist
echo -e "${YELLOW}Checking firewall rules...${NC}"
if ! gcloud compute firewall-rules describe allow-swe-bench &> /dev/null; then
    echo "Creating firewall rule..."
    gcloud compute firewall-rules create allow-swe-bench \
        --allow tcp:8080,tcp:22 \
        --source-ranges=0.0.0.0/0 \
        --target-tags="$NETWORK_TAG" \
        --description="Allow access to SWE-Bench tester service"
else
    echo "Firewall rule already exists"
fi

# Startup script for worker instances
read -r -d '' STARTUP_SCRIPT << 'EOF' || true
#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
apt-get install -y docker.io docker-compose git

# Configure Docker
systemctl start docker
systemctl enable docker

# Add default user to docker group
usermod -aG docker $(whoami)

# Configure Docker daemon for better performance
cat > /etc/docker/daemon.json <<'DOCKER_EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "10"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  }
}
DOCKER_EOF

systemctl restart docker

# Pull and run the tester service
docker pull {DOCKER_IMAGE}
docker run -d \
  --name swe-bench-tester \
  --restart unless-stopped \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v swe-bench-cache:/cache \
  -e WORKERS=15 \
  -e LOG_LEVEL=INFO \
  {DOCKER_IMAGE}

# Log startup completion
echo "SWE-Bench worker ready at $(date)" > /var/log/swe-bench-startup.log
EOF

# Replace placeholder in startup script
STARTUP_SCRIPT="${STARTUP_SCRIPT//\{DOCKER_IMAGE\}/$DOCKER_IMAGE}"

# Create worker instances
echo -e "${YELLOW}Creating $NUM_WORKERS worker instances...${NC}"
for i in $(seq 1 "$NUM_WORKERS"); do
    instance_name="swe-bench-worker-$i"
    
    echo -e "Creating instance: ${GREEN}$instance_name${NC}"
    
    # Check if instance already exists
    if gcloud compute instances describe "$instance_name" --zone="$ZONE" &> /dev/null; then
        echo -e "${YELLOW}Instance $instance_name already exists, skipping...${NC}"
        continue
    fi
    
    # Create instance
    gcloud compute instances create "$instance_name" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size="$BOOT_DISK_SIZE" \
        --boot-disk-type=pd-ssd \
        --tags="$NETWORK_TAG" \
        --metadata=startup-script="$STARTUP_SCRIPT" \
        --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write \
        --maintenance-policy=MIGRATE \
        --async
done

# Wait for instances to be created
echo -e "${YELLOW}Waiting for instances to be created...${NC}"
sleep 30

# Get instance IPs
echo -e "${YELLOW}Getting instance IPs...${NC}"
WORKER_IPS=()
for i in $(seq 1 "$NUM_WORKERS"); do
    instance_name="swe-bench-worker-$i"
    
    # Get external IP
    IP=$(gcloud compute instances describe "$instance_name" \
        --zone="$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo "pending")
    
    WORKER_IPS+=("$IP")
    echo "  $instance_name: $IP"
done

# Wait for startup scripts to complete
echo -e "${YELLOW}Waiting for workers to initialize (this may take 2-3 minutes)...${NC}"
sleep 120

# Health check function
health_check() {
    local ip=$1
    local instance_name=$2
    
    if [ "$ip" == "pending" ]; then
        return 1
    fi
    
    if curl -s -f -m 5 "http://$ip:8080/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check health of all workers
echo -e "${YELLOW}Checking worker health...${NC}"
all_healthy=true
for i in $(seq 1 "$NUM_WORKERS"); do
    instance_name="swe-bench-worker-$i"
    ip="${WORKER_IPS[$i-1]}"
    
    if health_check "$ip" "$instance_name"; then
        echo -e "  ${GREEN}✓${NC} $instance_name ($ip) - Healthy"
    else
        echo -e "  ${RED}✗${NC} $instance_name ($ip) - Not responding"
        all_healthy=false
    fi
done

# Generate Python configuration
echo -e "${YELLOW}Generating Python configuration...${NC}"
cat > worker_config.py << PYEOF
# Auto-generated worker configuration
# Generated at: $(date)

from parallel_validator import WorkerNode

WORKER_FLEET = [
PYEOF

for i in $(seq 1 "$NUM_WORKERS"); do
    ip="${WORKER_IPS[$i-1]}"
    if [ "$ip" != "pending" ]; then
        cat >> worker_config.py << PYEOF
    WorkerNode(
        id="worker-$i",
        host="$ip",
        port=8080,
        assigned_repos=[],
        max_concurrent=15
    ),
PYEOF
    fi
done

cat >> worker_config.py << PYEOF
]

# Usage:
# from worker_config import WORKER_FLEET
# validator = ParallelValidator(workers=WORKER_FLEET)
PYEOF

echo -e "${GREEN}Worker configuration saved to worker_config.py${NC}"

# Summary
echo ""
echo -e "${GREEN}=== Deployment Summary ===${NC}"
echo "Workers created: $NUM_WORKERS"
echo "Machine type: $MACHINE_TYPE"
echo "Zone: $ZONE"
echo ""

if $all_healthy; then
    echo -e "${GREEN}All workers are healthy and ready!${NC}"
    echo ""
    echo "To run validation:"
    echo "  python parallel_validator.py --workers $NUM_WORKERS"
    echo ""
    echo "To destroy the fleet when done:"
    echo "  ./deploy_validation_fleet.sh --destroy"
else
    echo -e "${YELLOW}Some workers are not yet ready. Wait a few minutes and check:${NC}"
    echo "  for i in {1..$NUM_WORKERS}; do"
    echo "    curl -s http://\${WORKER_IPS[\$i-1]}:8080/health"
    echo "  done"
fi

# Handle destroy flag
if [ "${1:-}" == "--destroy" ]; then
    echo ""
    echo -e "${RED}=== Destroying Validation Fleet ===${NC}"
    read -p "Are you sure you want to destroy all worker instances? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for i in $(seq 1 "$NUM_WORKERS"); do
            instance_name="swe-bench-worker-$i"
            echo "Deleting $instance_name..."
            gcloud compute instances delete "$instance_name" --zone="$ZONE" --quiet || true
        done
        echo -e "${GREEN}Fleet destroyed${NC}"
    else
        echo "Destruction cancelled"
    fi
fi