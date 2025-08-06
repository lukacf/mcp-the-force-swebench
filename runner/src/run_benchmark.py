#!/usr/bin/env python3
"""Run SWE-Bench evaluation with Claude + The Force MCP."""

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import concurrent.futures
from dataclasses import dataclass

from fetch_data import load_instances, get_sample_instance
from evaluate_predictions import run_swebench_evaluation, quick_validate_predictions

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for SWE-Bench benchmark run."""

    # Execution settings
    with_mcp: bool = True  # Use The Force MCP tools
    max_workers: int = 1  # Parallel execution (start with 1 for testing)
    timeout_per_instance: int = 1800  # 30 minutes per instance

    # Data settings
    sample_size: Optional[int] = None  # Use all instances if None
    start_index: int = 0  # Skip first N instances

    # Output settings
    output_dir: str = "results"
    run_name: str = "claude-force-swe-bench"

    # Claude settings
    claude_command: str = "claude"  # Assumes claude CLI is in PATH
    system_prompt_file: str = "system_prompt.md"


def format_swe_task(instance: Dict[str, Any], with_mcp: bool = True) -> str:
    """Format SWE-Bench instance for Claude input."""

    task_description = f"""
# SWE-Bench Task: {instance['instance_id']}

## Repository
{instance['repo']}

## Problem Statement
{instance['problem_statement']}

## Your Mission
You are a software engineering agent. Analyze this issue, explore the repository, implement a fix, and provide a git diff.

"""

    if with_mcp:
        task_description += """
## Available Force Tools
You have access to The Force MCP tools:
- `chat_with_claude4_sonnet` - Deep analysis and implementation
- `chat_with_gpt41` - Fast processing with web search  
- `chat_with_gemini25_pro` - Complex reasoning and bug analysis
- `chat_with_o3` - Chain-of-thought reasoning
- `search_project_history` - Search past work
- Other utility tools for comprehensive analysis

Use these tools to get guidance, alternative perspectives, and validate your approach.

"""

    task_description += """
## Expected Output
When ready, provide your solution as:

```
SOLUTION_ANALYSIS:
[Brief explanation of the issue and your fix]

FINAL_PATCH:
[Complete git diff showing your changes]
```

Please proceed with analyzing and fixing this issue.
"""

    return task_description.strip()


def run_claude_on_task(
    task: str,
    instance_id: str,
    config: BenchmarkConfig,
    working_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Claude on a single SWE-Bench task."""

    start_time = time.time()

    try:
        # Create temporary file for task if needed
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(task)
            task_file = f.name

        # Prepare Claude command
        cmd = [config.claude_command, "-p", task]

        # System prompt should be pre-configured in Claude settings, not passed as argument
        # Claude CLI doesn't support -s flag for system prompts

        logger.info(f"Running Claude on {instance_id}...")
        logger.debug(f"Command: {' '.join(cmd[:3])}...")  # Don't log full task

        # Execute Claude
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_per_instance,
            cwd=working_dir,
        )

        duration = time.time() - start_time

        # Process result
        if result.returncode == 0:
            response = result.stdout

            # Extract solution and patch
            solution_analysis = ""
            final_patch = ""

            lines = response.split("\n")
            in_solution = False
            in_patch = False

            for line in lines:
                if "SOLUTION_ANALYSIS:" in line:
                    in_solution = True
                    in_patch = False
                    continue
                elif "FINAL_PATCH:" in line:
                    in_solution = False
                    in_patch = True
                    continue

                if in_solution:
                    solution_analysis += line + "\n"
                elif in_patch:
                    final_patch += line + "\n"

            return {
                "instance_id": instance_id,
                "success": True,
                "duration": duration,
                "response": response,
                "solution_analysis": solution_analysis.strip(),
                "prediction": final_patch.strip(),  # SWE-Bench format
                "model": f"claude-{config.run_name}",
                "with_mcp": config.with_mcp,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            logger.error(f"Claude failed on {instance_id}: {result.stderr}")
            return {
                "instance_id": instance_id,
                "success": False,
                "duration": duration,
                "error": result.stderr,
                "model": f"claude-{config.run_name}",
                "with_mcp": config.with_mcp,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout on {instance_id} after {config.timeout_per_instance}s")
        return {
            "instance_id": instance_id,
            "success": False,
            "duration": config.timeout_per_instance,
            "error": "Timeout",
            "model": f"claude-{config.run_name}",
            "with_mcp": config.with_mcp,
        }

    except Exception as e:
        logger.error(f"Exception on {instance_id}: {e}")
        return {
            "instance_id": instance_id,
            "success": False,
            "duration": time.time() - start_time,
            "error": str(e),
            "model": f"claude-{config.run_name}",
            "with_mcp": config.with_mcp,
        }

    finally:
        # Cleanup
        if "task_file" in locals():
            try:
                os.unlink(task_file)
            except Exception:
                pass


def run_benchmark(config: BenchmarkConfig) -> Dict[str, Any]:
    """Run the complete SWE-Bench benchmark."""

    logger.info(f"Starting SWE-Bench benchmark: {config.run_name}")
    logger.info(f"MCP enabled: {config.with_mcp}")
    logger.info(f"Max workers: {config.max_workers}")

    # Load instances
    instances = load_instances()
    if config.sample_size:
        instances = instances[
            config.start_index : config.start_index + config.sample_size
        ]
    else:
        instances = instances[config.start_index :]

    logger.info(f"Processing {len(instances)} instances")

    # Create output directory
    output_dir = Path(config.output_dir)
    output_dir.mkdir(exist_ok=True)

    results = []
    successful = 0
    failed = 0

    # Process instances
    if config.max_workers == 1:
        # Sequential processing for debugging
        for i, instance in enumerate(instances, 1):
            logger.info(f"Processing {i}/{len(instances)}: {instance['instance_id']}")

            task = format_swe_task(instance, config.with_mcp)
            result = run_claude_on_task(task, instance["instance_id"], config)

            results.append(result)

            if result["success"]:
                successful += 1
                logger.info(f"✅ Success: {instance['instance_id']}")
            else:
                failed += 1
                logger.error(f"❌ Failed: {instance['instance_id']}")

            # Save intermediate results
            if i % 5 == 0:
                save_results(results, output_dir, config)

    else:
        # Parallel processing
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.max_workers
        ) as executor:
            future_to_instance = {}

            for instance in instances:
                task = format_swe_task(instance, config.with_mcp)
                future = executor.submit(
                    run_claude_on_task, task, instance["instance_id"], config
                )
                future_to_instance[future] = instance

            for future in concurrent.futures.as_completed(future_to_instance):
                instance = future_to_instance[future]
                try:
                    result = future.result()
                    results.append(result)

                    if result["success"]:
                        successful += 1
                        logger.info(f"✅ Success: {instance['instance_id']}")
                    else:
                        failed += 1
                        logger.error(f"❌ Failed: {instance['instance_id']}")

                except Exception as e:
                    logger.error(f"Exception processing {instance['instance_id']}: {e}")
                    failed += 1

    # Save final results
    save_results(results, output_dir, config)

    # Generate summary
    summary = {
        "run_name": config.run_name,
        "with_mcp": config.with_mcp,
        "total_instances": len(instances),
        "successful": successful,
        "failed": failed,
        "success_rate": successful / len(instances) if instances else 0,
        "timestamp": time.time(),
    }

    logger.info("Benchmark complete!")
    logger.info(
        f"Success rate: {summary['success_rate']:.1%} ({successful}/{len(instances)})"
    )

    return summary


def save_results(
    results: List[Dict[str, Any]], output_dir: Path, config: BenchmarkConfig
):
    """Save results in SWE-Bench format."""

    # Save detailed results
    detailed_file = output_dir / f"{config.run_name}_detailed.jsonl"
    with open(detailed_file, "w") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    # Save SWE-Bench evaluation format (only successful predictions)
    eval_file = output_dir / f"{config.run_name}_predictions.jsonl"
    with open(eval_file, "w") as f:
        for result in results:
            if result["success"] and result.get("prediction"):
                swe_result = {
                    "instance_id": result["instance_id"],
                    "model_name_or_path": result["model"],
                    "prediction": result["prediction"],
                }
                f.write(json.dumps(swe_result) + "\n")

    logger.info(f"Results saved to {output_dir}")


def main():
    """CLI interface for SWE-Bench benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="Run SWE-Bench evaluation")
    parser.add_argument("--sample", type=int, help="Sample size for testing")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--workers", type=int, default=1, help="Max workers")
    parser.add_argument(
        "--timeout", type=int, default=1800, help="Timeout per instance (seconds)"
    )
    parser.add_argument(
        "--no-mcp", action="store_true", help="Run without MCP tools (baseline)"
    )
    parser.add_argument("--output-dir", default="results", help="Output directory")
    parser.add_argument("--run-name", help="Custom run name")
    parser.add_argument(
        "--test-single", action="store_true", help="Test with single instance"
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run evaluation after generating predictions",
    )
    parser.add_argument(
        "--quick-validate",
        action="store_true",
        help="Quick validation of predictions only",
    )

    args = parser.parse_args()

    # Test single instance
    if args.test_single:
        logger.info("Testing with single instance...")
        instance = get_sample_instance()
        if not instance:
            logger.error("No sample instance available")
            return

        config = BenchmarkConfig(
            with_mcp=not args.no_mcp,
            timeout_per_instance=args.timeout,
            run_name=args.run_name
            or f"test-{'with' if not args.no_mcp else 'without'}-mcp",
        )

        task = format_swe_task(instance, config.with_mcp)
        result = run_claude_on_task(task, instance["instance_id"], config)

        print(f"\nResult for {instance['instance_id']}:")
        print(f"Success: {result['success']}")
        print(f"Duration: {result['duration']:.1f}s")

        if result["success"]:
            print("\nSolution Analysis:")
            print(result.get("solution_analysis", "None"))
            print("\nPatch (first 500 chars):")
            print(result.get("prediction", "None")[:500])
        else:
            print(f"Error: {result.get('error', 'Unknown')}")

        return

    # Full benchmark
    config = BenchmarkConfig(
        with_mcp=not args.no_mcp,
        max_workers=args.workers,
        timeout_per_instance=args.timeout,
        sample_size=args.sample,
        start_index=args.start,
        output_dir=args.output_dir,
        run_name=args.run_name
        or f"claude-{'with' if not args.no_mcp else 'without'}-mcp",
    )

    summary = run_benchmark(config)

    print("\nBenchmark Summary:")
    print(f"Run: {summary['run_name']}")
    print(f"Generation Success Rate: {summary['success_rate']:.1%}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Total: {summary['total_instances']}")

    # Run evaluation if requested
    if args.evaluate and summary["successful"] > 0:
        print(f"\n{'='*50}")
        print("Running SWE-Bench Evaluation...")
        print(f"{'='*50}")

        predictions_file = (
            Path(config.output_dir) / f"{config.run_name}_predictions.jsonl"
        )

        if predictions_file.exists():
            try:
                eval_results = run_swebench_evaluation(
                    str(predictions_file),
                    max_workers=min(args.workers, 4),  # Limit workers for evaluation
                    run_id=f"{config.run_name}-eval",
                )

                print("\nEvaluation Results:")
                print(f"Success: {eval_results['success']}")

                if eval_results["success"]:
                    print(f"Resolved Issues: {eval_results.get('resolved', 0)}")
                    print(f"Total Issues: {eval_results.get('total', 0)}")
                    print(
                        f"SWE-Bench Score: {eval_results.get('success_rate', 0.0):.1%}"
                    )
                    print("🎯 Target: 70%+ (SOTA: 75.20%)")
                else:
                    print(
                        f"Evaluation failed: {eval_results.get('error', 'Unknown error')}"
                    )

            except Exception as e:
                print(f"Evaluation failed with exception: {e}")
                print("You can run evaluation manually with:")
                print(f"python evaluate_predictions.py {predictions_file}")
        else:
            print(f"No predictions file found: {predictions_file}")

    elif args.quick_validate:
        print(f"\n{'='*50}")
        print("Quick Validation...")
        print(f"{'='*50}")

        predictions_file = (
            Path(config.output_dir) / f"{config.run_name}_predictions.jsonl"
        )

        if predictions_file.exists():
            try:
                val_results = quick_validate_predictions(str(predictions_file))

                print("Quick Validation Results:")
                print(f"Sample size: {val_results['sample_size']}")
                print(f"Valid predictions: {val_results['valid_predictions']}")
                print(f"Validation rate: {val_results['success_rate']:.1%}")

            except Exception as e:
                print(f"Validation failed: {e}")
        else:
            print(f"No predictions file found: {predictions_file}")


if __name__ == "__main__":
    main()
