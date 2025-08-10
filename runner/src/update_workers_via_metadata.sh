#!/bin/bash
# Update workers via GCP metadata + reboot (no SSH needed)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Updating Workers via Metadata + Reboot${NC}"
echo "=================================="

# Configuration
ZONE="us-central1-a"
PROJECT=$(gcloud config get-value project)
REPOSITORY_LOCATION="us-central1"

# First, let's create Artifact Registry if it doesn't exist
echo -e "${YELLOW}Setting up Artifact Registry...${NC}"
if ! gcloud artifacts repositories describe swebench --location=$REPOSITORY_LOCATION &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create swebench \
        --repository-format=docker \
        --location=$REPOSITORY_LOCATION \
        --description="SWE-Bench Docker images"
fi

# Configure Docker for Artifact Registry
echo -e "${YELLOW}Configuring Docker authentication...${NC}"
gcloud auth configure-docker ${REPOSITORY_LOCATION}-docker.pkg.dev --quiet

# Build and push the fixed tester image
IMAGE_TAG="${REPOSITORY_LOCATION}-docker.pkg.dev/${PROJECT}/swebench/swe-bench-tester:v2-fixed"
echo -e "${YELLOW}Building and pushing fixed tester image...${NC}"
echo "Image: $IMAGE_TAG"

cd ../docker/tester
docker build -t "$IMAGE_TAG" .
docker push "$IMAGE_TAG"
cd ../../src

echo -e "${GREEN}✅ Image pushed successfully${NC}"

# Create the new startup script
echo -e "${YELLOW}Creating updated startup script...${NC}"
cat > /tmp/worker-startup-fixed.sh << EOF
#!/bin/bash
set -euxo pipefail

# Install Docker if not present
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Create scratch directory
mkdir -p /mnt/disks/ssd/repos || true

# Stop and remove old tester container if running
docker rm -f swe-bench-tester || true

# Pull the fixed tester image
IMAGE="${IMAGE_TAG}"
docker pull "\$IMAGE"

# Run the fixed tester with proper mounts
docker run -d --name swe-bench-tester \\
    -p 8080:8080 \\
    -v /var/run/docker.sock:/var/run/docker.sock \\
    -v /mnt/disks/ssd/repos:/scratch/repos \\
    --restart unless-stopped \\
    "\$IMAGE"

# Pre-pull some common SWE-bench images
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-10097:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.pallets__flask-5014:latest &
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.sympy__sympy-13895:latest &

echo "Worker updated with fixed tester v2"
EOF

# Update metadata and reboot each worker
echo -e "${YELLOW}Updating workers...${NC}"
UPDATED=0
FAILED=0

for i in $(seq 1 8); do
    INSTANCE="swe-bench-worker-$i"
    echo -e "\n${GREEN}Updating $INSTANCE...${NC}"
    
    # Check if instance exists
    if ! gcloud compute instances describe "$INSTANCE" --zone="$ZONE" &>/dev/null; then
        echo -e "${RED}Instance $INSTANCE not found${NC}"
        ((FAILED++))
        continue
    fi
    
    # Update metadata with new startup script
    if gcloud compute instances add-metadata "$INSTANCE" \
        --zone "$ZONE" \
        --metadata-from-file startup-script=/tmp/worker-startup-fixed.sh; then
        echo "  ✅ Metadata updated"
        
        # Reboot the instance
        echo "  🔄 Rebooting instance..."
        if gcloud compute instances reset "$INSTANCE" --zone "$ZONE"; then
            echo "  ✅ Reboot initiated"
            ((UPDATED++))
        else
            echo -e "  ${RED}Failed to reboot${NC}"
            ((FAILED++))
        fi
    else
        echo -e "  ${RED}Failed to update metadata${NC}"
        ((FAILED++))
    fi
done

# Clean up
rm -f /tmp/worker-startup-fixed.sh

echo -e "\n${YELLOW}Waiting for workers to come back online...${NC}"
echo "This may take 2-3 minutes per worker..."

# Wait a bit for instances to start rebooting
sleep 30

# Check worker health
echo -e "\n${YELLOW}Checking worker health...${NC}"
HEALTHY=0
MAX_ATTEMPTS=20

for i in $(seq 1 8); do
    INSTANCE="swe-bench-worker-$i"
    
    # Get IP address
    IP=$(gcloud compute instances describe "$INSTANCE" --zone "$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo "")
    
    if [ -z "$IP" ]; then
        echo -e "${RED}❌ Worker $i - No IP found${NC}"
        continue
    fi
    
    # Try to check health with retries
    echo -n "Worker $i ($IP): "
    SUCCESS=false
    
    for attempt in $(seq 1 $MAX_ATTEMPTS); do
        if curl -sf "http://$IP:8080/health" > /dev/null; then
            echo -e "${GREEN}✅ Healthy${NC}"
            ((HEALTHY++))
            SUCCESS=true
            break
        else
            echo -n "."
            sleep 10
        fi
    done
    
    if [ "$SUCCESS" = false ]; then
        echo -e " ${RED}❌ Not responding${NC}"
    fi
done

# Summary
echo -e "\n=================================="
echo -e "${GREEN}Update Summary:${NC}"
echo "- Workers updated: $UPDATED"
echo "- Workers failed: $FAILED"
echo "- Workers healthy: $HEALTHY/8"
echo ""

if [ $HEALTHY -ge 6 ]; then
    echo -e "${GREEN}✅ Enough workers are healthy to proceed with validation!${NC}"
    echo "The fixed tester is now running with:"
    echo "- python -m pytest (correct interpreter)"
    echo "- No --no-header flag"
    echo "- Increased timeouts (420s/300s)"
    echo "- Python version verification"
else
    echo -e "${RED}⚠️  Warning: Only $HEALTHY workers are healthy${NC}"
    echo "You may want to wait a bit longer or check the instances"
fi

echo "=================================="