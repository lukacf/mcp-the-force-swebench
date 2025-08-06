# MCP The Force - SWE-Bench Testing Infrastructure

A sophisticated testing infrastructure for running [SWE-Bench](https://www.swebench.com/) tasks using Claude and MCP The Force, which provides access to advanced AI models (o3, o3-pro, Gemini 2.5, GPT-4, etc.) for collaborative problem-solving.

## 🎯 Overview

This repository implements a complete SWE-Bench testing pipeline that:
- Uses Claude as the primary agent to solve coding problems
- Leverages MCP The Force to access multiple AI models for complex reasoning
- Executes tests locally or remotely on GCP using Epoch AI's pre-built Docker images
- Provides cost-effective infrastructure management with start/stop scripts

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Claude CLI    │────▶│   MCP The Force  │────▶│  AI Models      │
│   (Primary)     │     │   (Tool Server)  │     │  (o3, Gemini,   │
└─────────────────┘     └──────────────────┘     │   GPT-4, etc.)  │
         │                                        └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Local Runner   │────▶│  GCP Tester      │
│  (Git + Python) │     │  (Docker + API)  │
└─────────────────┘     └──────────────────┘
```

### Key Components

1. **Local Runner** (`runner/`)
   - Manages git repositories with efficient caching
   - Creates isolated Python environments
   - Applies patches and runs tests
   - Integrates with Claude and MCP tools

2. **MCP The Force Integration**
   - Provides access to state-of-the-art AI models
   - Enables complex reasoning and code analysis
   - Searches project history and documentation
   - Supports multi-model collaboration

3. **GCP Tester Service** (`runner/docker/tester/`)
   - FastAPI service running on Google Cloud
   - Uses Epoch AI's pre-built SWE-Bench Docker images
   - Executes patches in isolated containers
   - Returns test results via REST API

4. **Cost Management** (`scripts/gcp/`)
   - Start/stop scripts for GCP instances
   - ~$3/hour when running (c2-standard-60)
   - Automatic service restart on instance start

## 🚀 Quick Start

### Prerequisites
- Claude CLI installed and configured
- MCP The Force server running
- Google Cloud SDK (`gcloud`) configured
- Python 3.11+

### Setup

1. **Clone and setup the repository:**
```bash
git clone <your-repo-url>
cd mcp-the-force-swebench
./runner/bootstrap.sh
```

2. **Create GCP instance (one-time):**
```bash
./scripts/gcp/create-instance.sh
# Creates a c2-standard-60 instance with 500GB SSD
```

3. **Deploy tester service:**
```bash
./scripts/gcp/start-instance.sh
./scripts/gcp/deploy-tester-v2.sh
```

### Running SWE-Bench Tasks

```bash
# Start the GCP instance
./scripts/gcp/start-instance.sh

# Run a sample of 5 tasks
cd runner/src
python -m dispatcher --sample 5

# When done, stop the instance to save money
./scripts/gcp/stop-instance.sh
```

## 💰 Cost Management

The GCP instance costs ~$3/hour when running. Always remember to:
- Start the instance only when needed: `./scripts/gcp/start-instance.sh`
- Stop it when done: `./scripts/gcp/stop-instance.sh`
- Check status: `./scripts/gcp/status.sh`

## 📁 Repository Structure

```
mcp-the-force-swebench/
├── README.md               # This file
├── .gitignore             # Comprehensive ignore patterns
├── claude_hooks/          # Logging and monitoring hooks
├── runner/                # Main SWE-Bench runner system
│   ├── src/              # Core Python modules
│   ├── scripts/          # Utility scripts
│   ├── docker/           # Tester service Docker config
│   ├── artifacts/        # Git cache (1.7GB when populated)
│   ├── CLAUDE.md         # Instructions for Claude
│   └── README.md         # Runner-specific documentation
└── scripts/              # Infrastructure management
    └── gcp/             # GCP instance control scripts
```

## 🔧 How It Works

1. **Problem Analysis**: Claude reads the SWE-Bench task and uses MCP tools to:
   - Search codebases with `search_project_history`
   - Analyze complex code with `chat_with_o3` or `chat_with_gemini25_pro`
   - Get web documentation with `WebSearch`

2. **Solution Development**: Claude develops a fix by:
   - Creating a git worktree from cached repository
   - Setting up Python environment
   - Writing and testing patches iteratively
   - Using AI models for complex reasoning

3. **Testing**: Patches are tested either:
   - **Locally**: Direct pytest execution in worktrees
   - **Remotely**: Via GCP tester service using Epoch AI Docker images

4. **Iteration**: Claude refines the solution based on test results

## 🛠️ Advanced Features

### MCP The Force Tools
- `chat_with_o3`: Chain-of-thought reasoning (200k context)
- `chat_with_o3_pro`: Deep analysis and formal reasoning
- `chat_with_gemini25_pro`: Multimodal analysis
- `search_project_history`: Search past decisions and commits
- `research_with_o3_deep_research`: Ultra-deep research (10-60 min)

### Git Caching System
- Bare repository mirrors for efficiency
- Lightweight worktrees for each task
- Automatic cleanup after completion
- ~30-60x faster than fresh clones

### Remote Testing
- Supports all 500 Epoch AI pre-built images
- Automatic pytest installation in containers
- Proper exit code handling
- Test patch support for bug verification

## 📊 Performance

| Operation | Without Cache | With Cache | Speedup |
|-----------|--------------|------------|---------|
| Git Clone | 30-60s | <1s (worktree) | 30-60x |
| Total Setup | 75-240s | <5s | 15-48x |

## 🤝 Contributing

This project uses:
- Claude hooks for logging to VictoriaLogs
- Git worktrees for isolation
- FastAPI for the tester service
- Comprehensive error handling

## 📝 Notes

- The `runner/artifacts/` directory contains a 1.7GB git cache (preserved during cleanup)
- All Epoch AI Docker images are pulled on-demand by the GCP instance
- The system handles both successful and failing tests properly
- Exit codes are properly propagated from Docker containers

## 🔒 Security

- No credentials are stored in the repository
- GCP instance uses service account authentication
- Docker socket is mounted read-only where possible
- All patches are validated before execution

---

Built to push the boundaries of AI-assisted software development using SWE-Bench as a benchmark.