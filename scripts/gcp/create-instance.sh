#!/bin/bash
# Create a new GCP instance for SWE-Bench testing

set -e

# Configuration
INSTANCE_NAME="${INSTANCE_NAME:-swe-bench-beast}"
ZONE="${ZONE:-us-central1-a}"
MACHINE_TYPE="${MACHINE_TYPE:-c2-standard-60}"  # 60 vCPUs
DISK_SIZE="${DISK_SIZE:-500}"  # GB
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

echo "🔧 Creating GCP instance for SWE-Bench testing..."
echo ""
echo "Configuration:"
echo "  Instance: $INSTANCE_NAME"
echo "  Zone: $ZONE"
echo "  Machine Type: $MACHINE_TYPE"
echo "  Disk Size: ${DISK_SIZE}GB"
echo ""

# Confirm with user for expensive instance
if [[ "$MACHINE_TYPE" == *"60"* ]] || [[ "$MACHINE_TYPE" == *"96"* ]]; then
    echo "⚠️  WARNING: This is an expensive instance type (~\$3/hour)!"
    read -p "Are you sure you want to create this instance? (yes/no): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi
fi

# Create the instance
echo "📦 Creating instance..."
gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type=pd-ssd \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --maintenance-policy=MIGRATE \
    --tags=swe-bench-tester \
    --metadata=startup-script='#!/bin/bash
# Install Docker
apt-get update
apt-get install -y docker.io git
usermod -aG docker $USER

# Create directory for repos
mkdir -p /scratch/repos
chmod 777 /scratch/repos
'

echo "🔥 Creating firewall rule for port 8080..."
gcloud compute firewall-rules create swe-bench-tester-8080 \
    --allow tcp:8080 \
    --target-tags swe-bench-tester \
    --description "Allow access to SWE-Bench tester service" \
    2>/dev/null || echo "Firewall rule already exists"

# Wait for instance to be ready
echo "⏳ Waiting for instance to be ready..."
sleep 30

# Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "✅ Instance created successfully!"
echo "🌐 External IP: $EXTERNAL_IP"
echo ""
echo "Next steps:"
echo "1. Deploy tester service: ./scripts/gcp/deploy-tester-v2.sh"
echo "2. Stop instance when done: ./scripts/gcp/stop-instance.sh"
echo ""
echo "💰 Remember: This instance costs ~\$3/hour while running!"