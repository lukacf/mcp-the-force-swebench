#!/usr/bin/env python3
"""Generate solutions for SWE-Bench instances using Claude + The Force MCP."""

import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import concurrent.futures
from dataclasses import dataclass

from fetch_data import load_instances, get_sample_instance

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def clean_patch(raw: str) -> str:
    """O3's battle-tested patch cleaner - handles all common formatting issues."""
    import re
    import unicodedata
    
    if not raw or not raw.strip():
        return ""
    
    # Remove markdown code-block fences
    raw = re.sub(r'```diff\s*|```$', '', raw.strip(), flags=re.DOTALL)
    
    # Normalise Unicode – guards against smart quotes
    raw = unicodedata.normalize('NFKC', raw)
    
    # Strip CR characters (Windows line endings)
    raw = raw.replace('\r', '')
    
    # Ensure final newline
    if not raw.endswith('\n'):
        raw += '\n'
    
    return raw


def validate_and_clean_patch(patch: str, instance_id: str) -> str:
    """Apply O3's cleaning and validation pipeline."""
    
    if not patch or not patch.strip():
        return ""
    
    # First, apply O3's proven cleaning
    cleaned = clean_patch(patch)
    
    # O3's automatic guard check
    if not cleaned.startswith('diff --git'):
        logger.warning(f"Patch for {instance_id} doesn't start with 'diff --git'")
        return ""
    
    # Additional validation for essential diff elements
    if not ('@@' in cleaned or 'new file mode' in cleaned or 'deleted file mode' in cleaned):
        logger.warning(f"Patch for {instance_id} missing essential diff elements")
        return ""
    
    return cleaned


@dataclass
class SolveConfig:
    """Configuration for SWE-Bench solution generation."""
    
    # Execution settings
    with_mcp: bool = True  # Use The Force MCP tools
    max_workers: int = 1   # Parallel execution
    timeout_per_instance: int = 1800  # 30 minutes per instance
    
    # Data settings
    sample_size: Optional[int] = None  # Use all instances if None
    start_index: int = 0  # Skip first N instances
    
    # Output settings
    base_output_dir: str = "runs"
    run_name: Optional[str] = None  # Auto-generate if None
    
    # Claude settings
    claude_command: str = "claude"  # Assumes claude CLI is in PATH
    system_prompt_file: str = "system_prompt.md"


def get_next_run_name(base_dir: Path) -> str:
    """Generate next run name (run-00001, run-00002, etc.)."""
    
    base_dir.mkdir(exist_ok=True)
    
    # Find existing run directories
    existing_runs = [d.name for d in base_dir.iterdir() 
                    if d.is_dir() and d.name.startswith("run-")]
    
    if not existing_runs:
        return "run-00001"
    
    # Extract numbers and find max
    numbers = []
    for run_name in existing_runs:
        try:
            num = int(run_name.split("-")[1])
            numbers.append(num)
        except (IndexError, ValueError):
            continue
    
    if not numbers:
        return "run-00001"
    
    next_num = max(numbers) + 1
    return f"run-{next_num:05d}"


def get_latest_run_name(base_dir: Path) -> Optional[str]:
    """Get the most recent run directory."""
    
    if not base_dir.exists():
        return None
    
    run_dirs = [d for d in base_dir.iterdir() 
               if d.is_dir() and d.name.startswith("run-")]
    
    if not run_dirs:
        return None
    
    # Sort by modification time (most recent first)
    latest_dir = max(run_dirs, key=lambda d: d.stat().st_mtime)
    return latest_dir.name


def format_swe_task(instance: Dict[str, Any], with_mcp: bool = True) -> str:
    """Clear task with explicit diff requirement and ultrathink trigger."""
    
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


def extract_diff_from_response(text: str) -> str:
    """Extract git diff from either XML tags or markdown code blocks."""
    import re
    
    # First try: Look for XML tags (case insensitive, multiline)
    xml_pattern = r'<FINAL_DIFF>(.*?)</FINAL_DIFF>'
    xml_match = re.search(xml_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if xml_match:
        diff_content = xml_match.group(1).strip()
        return diff_content
    
    # Second try: Look for markdown code blocks with diff
    # Pattern for ```diff ... ``` blocks
    markdown_pattern = r'```diff\s*\n(.*?)\n```'
    markdown_match = re.search(markdown_pattern, text, re.DOTALL)
    
    if markdown_match:
        diff_content = markdown_match.group(1).strip()
        return diff_content
    
    # Third try: Look for any code block that starts with 'diff --git'
    code_block_pattern = r'```[a-zA-Z]*\s*\n(diff --git.*?)\n```'
    code_match = re.search(code_block_pattern, text, re.DOTALL)
    
    if code_match:
        diff_content = code_match.group(1).strip()
        return diff_content
    
    # Fourth try: Look for raw diff that starts with 'diff --git' (no code blocks)
    raw_diff_pattern = r'^(diff --git.*?)(?=\n\n|\Z)'
    raw_match = re.search(raw_diff_pattern, text, re.MULTILINE | re.DOTALL)
    
    if raw_match:
        diff_content = raw_match.group(1).strip()
        return diff_content
    
    # Fallback: no diff found
    return ""


def extract_summary_from_response(text: str) -> str:
    """Extract problem-solving summary from XML tags."""
    import re
    
    # Look for SUMMARY XML tags (case insensitive, multiline)
    summary_pattern = r'<SUMMARY>(.*?)</SUMMARY>'
    summary_match = re.search(summary_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if summary_match:
        summary_content = summary_match.group(1).strip()
        return summary_content
    
    # No summary found
    return ""


def run_claude_on_instance(
    instance: Dict[str, Any], 
    config: SolveConfig,
    instance_number: int,
    run_id: str = None
) -> Dict[str, Any]:
    """Run Claude on a single SWE-Bench instance."""
    
    instance_id = instance['instance_id']
    start_time = time.time()
    
    # Generate unique run ID for this instance
    if run_id is None:
        run_id = f"swe-{instance_id}-{int(start_time)}"
    
    logger.info(f"Processing instance {instance_number}: {instance_id} (run_id: {run_id})")
    
    try:
        # Format task (simple prompt, let CLAUDE.md guide the format)
        task = format_swe_task(instance, config.with_mcp)
        
        # Get hooks directory path
        hooks_dir = os.path.join(os.path.dirname(__file__), "claude_hooks")
        
        # Simple Claude command - no system prompt constraints, let CLAUDE.md handle format
        cmd = [
            config.claude_command,
            "--dangerously-skip-permissions",
            "-p",
            task
        ]
        
        logger.info(f"Running Claude on {instance_id}...")
        logger.info(f"EXACT COMMAND: {' '.join(repr(arg) for arg in cmd)}")
        
        # Set up environment for hooks
        hook_env = os.environ.copy()
        hook_env.update({
            "RUN_ID": run_id,
            "INSTANCE_ID": instance_id,
            "VL_ENDPOINT": os.getenv("VL_ENDPOINT", "http://localhost:9428/insert/elasticsearch/_bulk"),
            "DEBUG_HOOKS": os.getenv("DEBUG_HOOKS", "false"),
            "CLAUDE_HOOKS_DIR": hooks_dir
        })
        
        # Execute Claude with hooks environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_per_instance,
            env=hook_env
        )
        
        duration = time.time() - start_time
        
        # Process result
        if result.returncode == 0:
            response = result.stdout.strip()
            
            logger.info(f"Raw Claude output for {instance_id} (first 200 chars): {response[:200]}...")
            
            # Extract diff from response (XML tags, markdown, or raw)
            raw_diff = extract_diff_from_response(response)
            
            # Extract summary from response (for debugging and visibility)
            problem_solving_summary = extract_summary_from_response(response)
            
            if raw_diff:
                # Apply O3's cleaning pipeline to the extracted diff
                final_patch = validate_and_clean_patch(raw_diff, instance_id)
                solution_analysis = "Diff extracted with ultrathink process"
            else:
                logger.warning(f"No diff found in output for {instance_id}")
                final_patch = ""
                solution_analysis = "No diff found in response"
            
            # Determine if this is actually successful
            has_valid_patch = bool(final_patch and final_patch.strip())
            
            return {
                "instance_id": instance_id,
                "instance_number": instance_number,
                "problem_statement": instance['problem_statement'],
                "repo": instance['repo'], 
                "base_commit": instance.get('base_commit', ''),
                "success": has_valid_patch,  # Only successful if we have a patch
                "duration": duration,
                "response": response,
                "solution_analysis": solution_analysis.strip(),
                "problem_solving_summary": problem_solving_summary.strip() if problem_solving_summary else "",
                "prediction": final_patch.strip(),
                "model": f"claude-ultrathink-{'with' if config.with_mcp else 'without'}-mcp",
                "timestamp": datetime.now().isoformat(),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "failure_reason": "No valid diff generated" if not has_valid_patch else None
            }
        else:
            logger.error(f"Claude failed on {instance_id}: {result.stderr}")
            return {
                "instance_id": instance_id,
                "instance_number": instance_number,
                "problem_statement": instance['problem_statement'],
                "repo": instance['repo'],
                "base_commit": instance.get('base_commit', ''),
                "success": False,
                "duration": duration,
                "error": result.stderr,
                "model": f"claude-ultrathink-{'with' if config.with_mcp else 'without'}-mcp",
                "timestamp": datetime.now().isoformat(),
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout on {instance_id} after {config.timeout_per_instance}s")
        return {
            "instance_id": instance_id,
            "instance_number": instance_number,
            "problem_statement": instance['problem_statement'],
            "repo": instance['repo'],
            "base_commit": instance.get('base_commit', ''),
            "success": False,
            "duration": config.timeout_per_instance,
            "error": "Timeout",
            "model": f"claude-xml-{'with' if config.with_mcp else 'without'}-mcp",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Exception on {instance_id}: {e}")
        return {
            "instance_id": instance_id,
            "instance_number": instance_number,
            "problem_statement": instance['problem_statement'],
            "repo": instance['repo'],
            "base_commit": instance.get('base_commit', ''),
            "success": False,
            "duration": time.time() - start_time,
            "error": str(e),
            "model": f"claude-xml-{'with' if config.with_mcp else 'without'}-mcp",
            "timestamp": datetime.now().isoformat()
        }


def save_instance_result(result: Dict[str, Any], run_dir: Path):
    """Save individual instance result to its own file."""
    
    instance_file = run_dir / f"instance-{result['instance_number']:03d}.json"
    
    with open(instance_file, 'w') as f:
        json.dump(result, f, indent=2)


def save_run_summary(results: List[Dict[str, Any]], run_dir: Path, config: SolveConfig):
    """Save run summary and metadata."""
    
    successful = sum(1 for r in results if r['success'])
    
    # Count instances with summaries
    instances_with_summaries = sum(1 for r in results if r.get('problem_solving_summary', '').strip())
    
    summary = {
        "run_name": run_dir.name,
        "model": f"claude-ultrathink-{'with' if config.with_mcp else 'without'}-mcp",
        "with_mcp": config.with_mcp,
        "ultrathink_enabled": True,
        "total_instances": len(results),
        "successful_predictions": successful,
        "failed_predictions": len(results) - successful,
        "success_rate": successful / len(results) if results else 0.0,
        "instances_with_summaries": instances_with_summaries,
        "summary_rate": instances_with_summaries / len(results) if results else 0.0,
        "config": {
            "max_workers": config.max_workers,
            "timeout_per_instance": config.timeout_per_instance,
            "sample_size": config.sample_size,
            "start_index": config.start_index
        },
        "timestamp": datetime.now().isoformat(),
        "instances": [
            {
                "instance_number": r['instance_number'],
                "instance_id": r['instance_id'],
                "success": r['success'],
                "duration": r['duration'],
                "has_summary": bool(r.get('problem_solving_summary', '').strip()),
                "file": f"instance-{r['instance_number']:03d}.json"
            }
            for r in results
        ]
    }
    
    # Save summary
    summary_file = run_dir / "run_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Run summary saved to {summary_file}")


def generate_predictions_file(run_dir: Path) -> Path:
    """Generate SWE-Bench compatible predictions file from instance files."""
    
    predictions = []
    instance_files = sorted(run_dir.glob("instance-*.json"))
    
    for instance_file in instance_files:
        with open(instance_file, 'r') as f:
            result = json.load(f)
        
        if result['success'] and result.get('prediction'):
            prediction = {
                "instance_id": result['instance_id'],
                "model_name_or_path": result['model'],
                "prediction": result['prediction']
            }
            predictions.append(prediction)
    
    # Save predictions file
    predictions_file = run_dir / "predictions.jsonl"
    with open(predictions_file, 'w') as f:
        for pred in predictions:
            f.write(json.dumps(pred) + '\n')
    
    logger.info(f"Generated {len(predictions)} predictions in {predictions_file}")
    return predictions_file


def run_solve(config: SolveConfig) -> str:
    """Run the complete solve process."""
    
    # Setup run directory
    base_dir = Path(config.base_output_dir)
    
    if config.run_name:
        run_name = config.run_name
        run_dir = base_dir / run_name
        if run_dir.exists():
            logger.warning(f"Overwriting existing run: {run_name}")
    else:
        run_name = get_next_run_name(base_dir)
        run_dir = base_dir / run_name
    
    run_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting solve run: {run_name}")
    logger.info(f"MCP enabled: {config.with_mcp}")
    logger.info(f"Max workers: {config.max_workers}")
    logger.info(f"Output directory: {run_dir}")
    
    # Load instances
    instances = load_instances()
    if config.sample_size:
        instances = instances[config.start_index:config.start_index + config.sample_size]
    else:
        instances = instances[config.start_index:]
    
    logger.info(f"Processing {len(instances)} instances")
    
    results = []
    
    # Process instances
    if config.max_workers == 1:
        # Sequential processing
        for i, instance in enumerate(instances, 1):
            result = run_claude_on_instance(instance, config, i)
            results.append(result)
            
            # Save individual result immediately
            save_instance_result(result, run_dir)
            
            if result['success']:
                logger.info(f"✅ Success: {instance['instance_id']}")
            else:
                logger.error(f"❌ Failed: {instance['instance_id']}")
    
    else:
        # Parallel processing with progress tracking
        logger.info(f"Using {config.max_workers} workers for parallel processing")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            future_to_instance = {}
            
            # Submit all tasks
            for i, instance in enumerate(instances, 1):
                future = executor.submit(run_claude_on_instance, instance, config, i)
                future_to_instance[future] = (instance, i)
            
            completed = 0
            total = len(instances)
            
            # Process completed tasks
            for future in concurrent.futures.as_completed(future_to_instance):
                instance, i = future_to_instance[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Save individual result immediately
                    save_instance_result(result, run_dir)
                    
                    if result['success']:
                        logger.info(f"✅ Success ({completed}/{total}): {instance['instance_id']} - {result['duration']:.1f}s")
                    else:
                        logger.error(f"❌ Failed ({completed}/{total}): {instance['instance_id']} - {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"💥 Exception ({completed}/{total}): {instance['instance_id']} - {e}")
                    # Create a failure result
                    failure_result = {
                        "instance_id": instance['instance_id'],
                        "instance_number": i,
                        "success": False,
                        "duration": 0,
                        "error": str(e),
                        "model": f"claude-{'with' if config.with_mcp else 'without'}-mcp",
                        "timestamp": datetime.now().isoformat()
                    }
                    results.append(failure_result)
                    save_instance_result(failure_result, run_dir)
    
    # Sort results by instance number
    results.sort(key=lambda r: r['instance_number'])
    
    # Save run summary
    save_run_summary(results, run_dir, config)
    
    # Generate predictions file  
    predictions_file = generate_predictions_file(run_dir)
    
    # Final summary
    successful = sum(1 for r in results if r['success'])
    logger.info(f"Solve run complete!")
    logger.info(f"Run: {run_name}")
    logger.info(f"Success rate: {successful/len(results):.1%} ({successful}/{len(results)})")
    logger.info(f"Results saved in: {run_dir}")
    logger.info(f"Predictions file: {predictions_file}")
    
    return run_name


def main():
    """CLI interface for solve."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SWE-Bench solutions")
    parser.add_argument("--sample", type=int, help="Sample size for testing")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--workers", type=int, default=1, help="Max workers")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout per instance (seconds)")
    parser.add_argument("--no-mcp", action="store_true", help="Run without MCP tools (baseline)")
    parser.add_argument("--run-name", help="Custom run name (auto-generated if not provided)")
    parser.add_argument("--output-dir", default="runs", help="Base output directory")
    parser.add_argument("--test-single", action="store_true", help="Test with single instance")
    
    args = parser.parse_args()
    
    # Test single instance
    if args.test_single:
        logger.info("Testing with single instance...")
        instance = get_sample_instance()
        if not instance:
            logger.error("No sample instance available")
            return
        
        config = SolveConfig(
            with_mcp=not args.no_mcp,
            timeout_per_instance=args.timeout,
            sample_size=1,
            run_name=args.run_name or "test-single"
        )
        
        # Setup run directory for single test
        base_dir = Path(config.base_output_dir)
        run_name = config.run_name if config.run_name else get_next_run_name(base_dir)
        run_dir = base_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Single test run directory: {run_dir}")
        
        result = run_claude_on_instance(instance, config, 1)
        
        # Save result to disk
        save_instance_result(result, run_dir)
        save_run_summary([result], run_dir, config)
        
        print(f"\nResult for {instance['instance_id']}:")
        print(f"Success: {result['success']}")
        print(f"Duration: {result['duration']:.1f}s")
        print(f"Results saved to: {run_dir}")
        
        if result['success']:
            print(f"\nSolution Analysis:")
            print(result.get('solution_analysis', 'None')[:300] + "...")
            
            # Show summary if available
            if result.get('problem_solving_summary'):
                print(f"\nProblem Solving Summary:")
                print(result.get('problem_solving_summary', 'None')[:400] + "...")
            
            print(f"\nPatch (first 200 chars):")
            print(result.get('prediction', 'None')[:200] + "...")
        else:
            print(f"Error: {result.get('error', 'Unknown')}")
        
        return
    
    # Full solve run
    config = SolveConfig(
        with_mcp=not args.no_mcp,
        max_workers=args.workers,
        timeout_per_instance=args.timeout,
        sample_size=args.sample,
        start_index=args.start,
        base_output_dir=args.output_dir,
        run_name=args.run_name
    )
    
    run_name = run_solve(config)
    
    print(f"\n🎉 Solve run complete: {run_name}")
    print(f"Next step: python evaluate.py --run {run_name}")
    print(f"Or just: python evaluate.py  (picks latest run)")


if __name__ == "__main__":
    main()