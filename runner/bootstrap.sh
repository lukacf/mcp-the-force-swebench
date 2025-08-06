#!/bin/bash
# Bootstrap script for SWE-Bench runner

set -e

echo "🚀 Bootstrapping SWE-Bench runner..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create artifact directories
echo "📁 Creating artifact directories..."
mkdir -p artifacts/{cache,worktrees,runs,results,evaluations}

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Verify Claude CLI is available
echo "🔍 Checking Claude CLI..."
if ! command -v claude &> /dev/null; then
    echo "❌ Error: Claude CLI not found in PATH"
    echo "Please install Claude CLI first"
    exit 1
fi
echo "✅ Claude CLI found"

# Check for MCP configuration
echo "🔍 Checking MCP configuration..."
if [ ! -d "../.mcp-the-force" ]; then
    echo "❌ Error: .mcp-the-force directory not found in parent directory"
    echo "Please ensure MCP The Force is configured"
    exit 1
fi
echo "✅ MCP configuration found"

# Run a quick smoke test
echo "🧪 Running smoke test..."
cd "$SCRIPT_DIR"
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
try:
    import dispatcher
    import worker
    import git_utils
    import test_runner
    import fetch_data
    import claude_force_client
    import patch_utils
    print('✅ All modules imported successfully')
except Exception as e:
    print(f'❌ Import error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

echo ""
echo "✨ Bootstrap complete!"
echo ""
echo "To run a test with 5 instances:"
echo "  cd src && python -m dispatcher --sample 5"
echo ""
echo "To run the full benchmark:"
echo "  cd src && python -m dispatcher --workers 4"