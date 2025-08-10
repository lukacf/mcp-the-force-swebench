#!/bin/bash
# Deploy a fleet of GCP instances for parallel SWE-Bench validation

set -e

# Configuration
NUM_WORKERS=${NUM_WORKERS:-8}
INSTANCE_TYPE="c2-standard-60"
ZONE="us-central1-a"
PROJECT=$(gcloud config get-value project)
DISK_SIZE="500GB"
DISK_TYPE="pd-ssd"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 SWE-Bench Validation Fleet Deployment${NC}"
echo "=================================="
echo "Workers: $NUM_WORKERS"
echo "Instance type: $INSTANCE_TYPE"
echo "Zone: $ZONE"
echo "Project: $PROJECT"
echo ""

# Check if we're destroying
if [ "$1" == "--destroy" ]; then
    echo -e "${YELLOW}⚠️  Destroying validation fleet...${NC}"
    for i in $(seq 1 $NUM_WORKERS); do
        instance_name="swe-bench-worker-$i"
        echo "Deleting $instance_name..."
        gcloud compute instances delete $instance_name --zone=$ZONE --quiet || true
    done
    echo -e "${GREEN}✅ Fleet destroyed${NC}"
    exit 0
fi

# Create startup script
cat > /tmp/worker-startup.sh << 'EOF'
#!/bin/bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repository
cd /home
git clone https://github.com/lukacf/mcp-the-force-swebench.git
cd mcp-the-force-swebench

# Build and run tester service
cd runner/docker/tester
docker build -t swe-bench-tester .
docker run -d --name swe-bench-tester \
    -p 8080:8080 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /mnt/disks/ssd/repos:/scratch/repos \
    swe-bench-tester

# Pre-pull some common images to speed up first runs
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-10097:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.pallets__flask-5014:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.sympy__sympy-13895:latest &

echo "Worker ready!"
EOF

# Create instances
echo -e "${YELLOW}Creating $NUM_WORKERS worker instances...${NC}"
WORKER_IPS=()

for i in $(seq 1 $NUM_WORKERS); do
    instance_name="swe-bench-worker-$i"
    echo -e "\n${GREEN}Creating $instance_name...${NC}"
    
    # Check if instance already exists
    if gcloud compute instances describe $instance_name --zone=$ZONE &>/dev/null; then
        echo "Instance $instance_name already exists, getting IP..."
        IP=$(gcloud compute instances describe $instance_name --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    else
        # Create instance
        gcloud compute instances create $instance_name \
            --zone=$ZONE \
            --machine-type=$INSTANCE_TYPE \
            --boot-disk-size=$DISK_SIZE \
            --boot-disk-type=$DISK_TYPE \
            --image-family=ubuntu-2204-lts \
            --image-project=ubuntu-os-cloud \
            --metadata-from-file startup-script=/tmp/worker-startup.sh \
            --tags=swe-bench-worker \
            --preemptible
        
        # Get IP
        IP=$(gcloud compute instances describe $instance_name --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    fi
    
    WORKER_IPS+=($IP)
    echo "Worker $i IP: $IP"
done

# Create firewall rule if needed
if ! gcloud compute firewall-rules describe allow-swe-bench-tester &>/dev/null; then
    echo -e "\n${YELLOW}Creating firewall rule...${NC}"
    gcloud compute firewall-rules create allow-swe-bench-tester \
        --allow tcp:8080 \
        --source-ranges 0.0.0.0/0 \
        --target-tags swe-bench-worker
fi

# Wait for workers to be ready
echo -e "\n${YELLOW}Waiting for workers to be ready...${NC}"
for i in $(seq 1 $NUM_WORKERS); do
    IP=${WORKER_IPS[$i-1]}
    echo -n "Worker $i ($IP): "
    
    # Wait up to 5 minutes for the service to be ready
    for j in {1..60}; do
        if curl -s -f "http://$IP:8080/health" &>/dev/null; then
            echo -e "${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 5
    done
    
    if ! curl -s -f "http://$IP:8080/health" &>/dev/null; then
        echo -e "${RED}Failed to start!${NC}"
    fi
done

# Generate worker configuration
echo -e "\n${YELLOW}Generating worker configuration...${NC}"
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
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo -e "${GREEN}✅ Worker configuration saved to worker_config.json${NC}"

# Cleanup
rm -f /tmp/worker-startup.sh

# Summary
echo ""
echo -e "${GREEN}=================================="
echo "🎉 Validation Fleet Ready!"
echo "=================================="
echo "Workers: $NUM_WORKERS"
echo "Total vCPUs: $((NUM_WORKERS * 60))"
echo "Total RAM: $((NUM_WORKERS * 240))GB"
echo "Cost: ~\$$(echo "$NUM_WORKERS * 3" | bc)/hour"
echo ""
echo "To run validation:"
echo "  cd runner/src"
echo "  python parallel_validator.py"
echo ""
echo "To destroy fleet when done:"
echo "  $0 --destroy"
echo "=================================="
echo -e "${NC}"