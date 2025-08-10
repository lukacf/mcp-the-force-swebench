#!/bin/bash
# Deploy fixed tester service to all GCP workers

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Deploying Fixed Tester Service${NC}"
echo "=================================="

# Load worker config
if [ ! -f "worker_config.json" ]; then
    echo -e "${RED}ERROR: worker_config.json not found!${NC}"
    exit 1
fi

# Extract worker IPs
WORKER_IPS=($(cat worker_config.json | grep http | cut -d'"' -f2 | cut -d'/' -f3 | cut -d':' -f1))
echo "Found ${#WORKER_IPS[@]} workers to update"

# Build the fixed tester image locally
echo -e "\n${YELLOW}Building fixed tester image...${NC}"
cd ../docker/tester
docker build -t swe-bench-tester-fixed:latest .
cd ../../src

# Save the image to tar
echo -e "${YELLOW}Saving Docker image...${NC}"
docker save swe-bench-tester-fixed:latest -o /tmp/swe-bench-tester-fixed.tar

# Deploy to each worker
for i in "${!WORKER_IPS[@]}"; do
    IP=${WORKER_IPS[$i]}
    WORKER_NUM=$((i+1))
    
    echo -e "\n${GREEN}Deploying to Worker $WORKER_NUM ($IP)...${NC}"
    
    # Copy the Docker image
    echo "  - Copying Docker image..."
    scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        /tmp/swe-bench-tester-fixed.tar ${USER}@${IP}:/tmp/ || {
        echo -e "${RED}  Failed to copy to $IP${NC}"
        continue
    }
    
    # Load image and restart container
    echo "  - Loading image and restarting service..."
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${USER}@${IP} << 'EOF'
        # Load the new image
        sudo docker load -i /tmp/swe-bench-tester-fixed.tar
        
        # Stop existing container
        sudo docker stop swe-bench-tester || true
        sudo docker rm swe-bench-tester || true
        
        # Start new container with fixed version
        sudo docker run -d --name swe-bench-tester \
            -p 8080:8080 \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v /mnt/disks/ssd/repos:/scratch/repos \
            --restart unless-stopped \
            swe-bench-tester-fixed:latest
        
        # Clean up
        rm -f /tmp/swe-bench-tester-fixed.tar
        
        # Verify it's running
        sleep 5
        if curl -s -f http://localhost:8080/health > /dev/null; then
            echo "✅ Tester service is running!"
        else
            echo "❌ Tester service failed to start!"
            exit 1
        fi
EOF
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✅ Worker $WORKER_NUM updated successfully${NC}"
    else
        echo -e "${RED}  ❌ Worker $WORKER_NUM update failed${NC}"
    fi
done

# Clean up local tar
rm -f /tmp/swe-bench-tester-fixed.tar

# Test all workers
echo -e "\n${YELLOW}Testing all workers...${NC}"
FAILED_WORKERS=()

for i in "${!WORKER_IPS[@]}"; do
    IP=${WORKER_IPS[$i]}
    WORKER_NUM=$((i+1))
    
    if curl -s -f "http://${IP}:8080/health" > /dev/null; then
        echo -e "${GREEN}✅ Worker $WORKER_NUM ($IP) - OK${NC}"
    else
        echo -e "${RED}❌ Worker $WORKER_NUM ($IP) - FAILED${NC}"
        FAILED_WORKERS+=($IP)
    fi
done

echo -e "\n=================================="
if [ ${#FAILED_WORKERS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All workers updated successfully!${NC}"
    echo -e "${GREEN}Ready to run validation with fixes.${NC}"
else
    echo -e "${RED}❌ ${#FAILED_WORKERS[@]} workers failed to update${NC}"
    echo "Failed workers: ${FAILED_WORKERS[@]}"
fi
echo "=================================="