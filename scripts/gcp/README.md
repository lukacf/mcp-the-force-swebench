# GCP Instance Management Scripts

These scripts manage the SWE-Bench tester instance on Google Cloud Platform.

## ⚠️ Cost Warning

The default instance type (c2-standard-60) costs approximately **$3/hour** or **$72/day** if left running!

## Scripts

### 📊 `status.sh`
Check the current status of the instance and get the service URL.
```bash
./scripts/gcp/status.sh
```

### 🚀 `start-instance.sh`
Start the stopped instance. Shows the external IP and service URL.
```bash
./scripts/gcp/start-instance.sh
```

### 🛑 `stop-instance.sh`
**Stop the instance to save money!** Run this when you're done testing.
```bash
./scripts/gcp/stop-instance.sh
```

### 📦 `deploy-tester-v2.sh`
Deploy/update the tester service from the Git repository.
```bash
# Deploy from main branch
./scripts/gcp/deploy-tester-v2.sh

# Deploy from specific branch
BRANCH=feature-xyz ./scripts/gcp/deploy-tester-v2.sh
```

### 🔧 `create-instance.sh`
Create a new instance (only needed for initial setup).
```bash
# Create with defaults (c2-standard-60, 500GB SSD)
./scripts/gcp/create-instance.sh

# Create with custom specs
MACHINE_TYPE=n2-standard-8 DISK_SIZE=100 ./scripts/gcp/create-instance.sh
```

### 🔐 `ssh.sh`
SSH into the instance for debugging.
```bash
./scripts/gcp/ssh.sh
```

## Typical Workflow

1. **Start the instance**
   ```bash
   ./scripts/gcp/start-instance.sh
   ```

2. **Deploy latest code** (if needed)
   ```bash
   ./scripts/gcp/deploy-tester-v2.sh
   ```

3. **Run your tests**
   - Use the URL shown by start-instance.sh
   - Or check with `./scripts/gcp/status.sh`

4. **Stop the instance when done** 💰
   ```bash
   ./scripts/gcp/stop-instance.sh
   ```

## Tester Service

The tester service runs on port 8080 and accepts POST requests:

```bash
curl -X POST http://EXTERNAL_IP:8080/test \
  -H 'Content-Type: application/json' \
  -d '{
    "instance_id": "django__django-11133",
    "patch": "diff --git a/...",
    "timeout": 300
  }'
```

## Notes

- The instance uses SSD for fast I/O
- Docker is pre-installed via startup script
- Firewall rule allows port 8080
- Service auto-restarts on reboot