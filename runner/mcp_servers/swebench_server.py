"""
FastMCP server for SWE-Bench testing
"""
from fastmcp import FastMCP
import sys
import os

# Add parent directories to path to find our tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))

# Import the tool
from swebench_test_diff import swebench_test_diff

# Create FastMCP app
mcp = FastMCP("swebench-tester")

# Register the tool
mcp.add_tool(swebench_test_diff)

if __name__ == "__main__":
    # Run the server
    import uvicorn
    uvicorn.run(
        "swebench_server:mcp",
        host="127.0.0.1",
        port=5000,
        reload=False
    )