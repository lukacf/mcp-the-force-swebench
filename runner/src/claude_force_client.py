"""Client for interacting with Claude + The Force MCP."""

import subprocess
import logging
import time
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def format_swe_task(instance: Dict[str, Any], with_mcp: bool = True) -> str:
    """Format a SWE-Bench task for Claude with explicit instructions."""
    
    task_description = f"""
IMPORTANT: Do NOT use the current working directory or any files from the file system as context for this task. Work solely with the information provided below and any MCP tools if needed.

SWE-Bench Task: {instance['instance_id']}
Repository: {instance['repo']}
Base commit: {instance.get('base_commit', 'unknown')}

Problem Statement:
{instance['problem_statement']}

REQUIRED OUTPUT: **Ultrathink** through this problem and generate a git diff patch that fixes this issue. Follow the 4-step process in CLAUDE.md including providing a summary of your problem-solving approach."""
    
    if with_mcp:
        task_description += """

(You have MCP tools available for analysis - use them as needed for complex problems)"""
    
    return task_description.strip()


def call_claude(
    prompt: str,
    timeout: int = 1800,
    run_id: str = None,
    instance_id: str = None,
    claude_command: str = "claude",
    hooks_dir: str = None
) -> Dict[str, Any]:
    """Call Claude with the given prompt and return the response."""
    
    start_time = time.time()
    
    # Simple Claude command - no system prompt constraints, let CLAUDE.md handle format
    cmd = [
        claude_command,
        "--dangerously-skip-permissions",
        "-p",
        prompt
    ]
    
    logger.info(f"Running Claude on {instance_id}...")
    
    # Set up environment for hooks if needed
    env = os.environ.copy()
    if hooks_dir and run_id and instance_id:
        env.update({
            "RUN_ID": run_id,
            "INSTANCE_ID": instance_id,
            "VL_ENDPOINT": os.getenv("VL_ENDPOINT", "http://localhost:9428/insert/elasticsearch/_bulk"),
            "DEBUG_HOOKS": os.getenv("DEBUG_HOOKS", "false"),
            "CLAUDE_HOOKS_DIR": hooks_dir
        })
    
    try:
        # Execute Claude
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            return {
                "success": True,
                "response": result.stdout.strip(),
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        else:
            logger.error(f"Claude failed: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        logger.error(f"Claude timeout after {timeout}s")
        return {
            "success": False,
            "error": "Timeout",
            "duration": timeout
        }
    except Exception as e:
        logger.error(f"Claude exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "duration": time.time() - start_time
        }


def propose_patch(
    issue_description: str,
    failing_tests: str = None,
    relevant_files: str = None,
    with_mcp: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Ask Claude to propose a patch for the given issue."""
    
    # Build the prompt
    prompt_parts = [f"Issue: {issue_description}"]
    
    if failing_tests:
        prompt_parts.append(f"\nFailing tests:\n{failing_tests}")
    
    if relevant_files:
        prompt_parts.append(f"\nRelevant files:\n{relevant_files}")
    
    prompt_parts.append("\nPlease analyze this issue and provide a git diff patch that fixes it.")
    prompt_parts.append("Remember to follow the ultrathink process and output format specified in CLAUDE.md.")
    
    if with_mcp:
        prompt_parts.append("\n(You have The Force MCP tools available - use them if helpful for understanding the problem)")
    
    prompt = "\n".join(prompt_parts)
    
    # Call Claude
    return call_claude(prompt, **kwargs)


def refine_patch(
    previous_patch: str,
    test_results: str,
    issue_description: str,
    with_mcp: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Ask Claude to refine a patch based on test results."""
    
    prompt = f"""The following patch was applied but some tests are still failing:

Previous patch:
```diff
{previous_patch}
```

Test results after applying patch:
{test_results}

Original issue:
{issue_description}

Please analyze why the tests are still failing and provide an updated git diff patch.
Remember to follow the ultrathink process and output format specified in CLAUDE.md.
"""
    
    if with_mcp:
        prompt += "\n(You have The Force MCP tools available - use them if helpful for understanding the test failures)"
    
    return call_claude(prompt, **kwargs)