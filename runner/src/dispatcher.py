"""Dispatcher for running SWE-Bench tasks in parallel."""

import json
import logging
import concurrent.futures
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from .worker import Worker
    from .fetch_data import load_instances
except ImportError:
    # For direct execution
    from worker import Worker
    from fetch_data import load_instances

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Dispatcher:
    """Manages parallel execution of SWE-Bench tasks."""
    
    def __init__(
        self,
        max_workers: int = 4,
        cache_dir: Path = None,
        output_dir: Path = None,
        with_mcp: bool = True,
        max_iterations: int = 5,
        timeout_per_iteration: int = 600,
        use_docker: bool = False
    ):
        self.max_workers = max_workers
        self.cache_dir = cache_dir or Path("runner/artifacts/cache")
        self.output_dir = output_dir or Path("runner/artifacts/results")
        self.with_mcp = with_mcp
        self.max_iterations = max_iterations
        self.timeout_per_iteration = timeout_per_iteration
        self.use_docker = use_docker or os.environ.get('SWEBENCH_USE_DOCKER', '0') == '1'
        
    def run(
        self,
        instances: List[Dict[str, Any]],
        run_name: Optional[str] = None
    ) -> str:
        """Run all instances and return the run name."""
        
        # Generate run name if not provided
        if not run_name:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            run_name = f"run-{timestamp}"
            
        # Create output directory
        run_dir = self.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Starting run: {run_name}")
        logger.info(f"Processing {len(instances)} instances with {self.max_workers} workers")
        
        # Create predictions file
        predictions_file = run_dir / "predictions.jsonl"
        
        # Process instances
        results = []
        
        if self.max_workers == 1:
            # Sequential processing
            for i, instance in enumerate(instances):
                logger.info(f"Processing {i+1}/{len(instances)}: {instance['instance_id']}")
                
                if self.use_docker:
                    result = self._run_worker_docker(instance)
                else:
                    worker = Worker(
                        cache_dir=self.cache_dir,
                        max_iterations=self.max_iterations,
                        timeout_per_iteration=self.timeout_per_iteration,
                        with_mcp=self.with_mcp
                    )
                    
                    result = worker.solve_task(instance)
                results.append(result)
                
                # Save result immediately
                self._save_result(result, run_dir, predictions_file)
                
                if result['success']:
                    logger.info(f"✅ Success: {instance['instance_id']} ({result['iterations']} iterations)")
                else:
                    logger.error(f"❌ Failed: {instance['instance_id']} - {result.get('error', 'Unknown error')}")
        else:
            # Parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_instance = {}
                
                for instance in instances:
                    if self.use_docker:
                        future = executor.submit(self._run_worker_docker, instance)
                    else:
                        worker = Worker(
                            cache_dir=self.cache_dir,
                            max_iterations=self.max_iterations,
                            timeout_per_iteration=self.timeout_per_iteration,
                            with_mcp=self.with_mcp
                        )
                        
                        future = executor.submit(worker.solve_task, instance)
                    future_to_instance[future] = instance
                
                # Process completed tasks
                completed = 0
                for future in concurrent.futures.as_completed(future_to_instance):
                    instance = future_to_instance[future]
                    completed += 1
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # Save result immediately
                        self._save_result(result, run_dir, predictions_file)
                        
                        if result['success']:
                            logger.info(f"✅ Success ({completed}/{len(instances)}): {instance['instance_id']} ({result['iterations']} iterations)")
                        else:
                            logger.error(f"❌ Failed ({completed}/{len(instances)}): {instance['instance_id']} - {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.error(f"💥 Exception ({completed}/{len(instances)}): {instance['instance_id']} - {e}")
                        
                        # Create failure result
                        result = {
                            "instance_id": instance['instance_id'],
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        results.append(result)
        
        # Save summary
        self._save_summary(results, run_dir, run_name)
        
        # Final stats
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Run complete: {run_name}")
        logger.info(f"Success rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
        
        return run_name
    
    def _save_result(self, result: Dict[str, Any], run_dir: Path, predictions_file: Path):
        """Save individual result and update predictions file."""
        
        # Save detailed result
        instance_file = run_dir / f"{result['instance_id']}.json"
        with open(instance_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Append to predictions file if successful
        if result['success'] and result.get('prediction'):
            prediction = {
                "instance_id": result['instance_id'],
                "model_name_or_path": result.get('model', 'claude-force'),
                "prediction": result['prediction']
            }
            
            with open(predictions_file, 'a') as f:
                f.write(json.dumps(prediction) + '\n')
    
    def _save_summary(self, results: List[Dict[str, Any]], run_dir: Path, run_name: str):
        """Save run summary."""
        
        successful = sum(1 for r in results if r['success'])
        
        summary = {
            "run_name": run_name,
            "timestamp": datetime.now().isoformat(),
            "total_instances": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "success_rate": successful / len(results) if results else 0.0,
            "with_mcp": self.with_mcp,
            "max_workers": self.max_workers,
            "max_iterations": self.max_iterations,
            "instances": [
                {
                    "instance_id": r['instance_id'],
                    "success": r['success'],
                    "duration": r.get('duration', 0),
                    "iterations": r.get('iterations', 0)
                }
                for r in results
            ]
        }
        
        summary_file = run_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
    
    def _run_worker_docker(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Run a worker in a Docker container."""
        
        # Build Docker command
        cmd = [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",  # Force x86_64 on Apple Silicon
            "--user", "claude",  # Run as claude user
            # Environment variables
            "--env", f"OPENAI_API_KEY={os.getenv('OPENAI_API_KEY', '')}",
            "--env", f"ANTHROPIC_API_KEY={os.getenv('ANTHROPIC_API_KEY', '')}",
            "--env", f"VL_ENDPOINT={os.getenv('VL_ENDPOINT', '')}",
            "--env", "PYTHONPATH=/app/runner/src",
            "--env", "CLAUDE_HOOKS_DIR=/home/claude/claude_hooks",
            "--env", "CLAUDE_DANGEROUSLY_ASSUME_YES=1",
            # Mount the cache volume
            "--volume", "runner_bench-cache:/app/runner/artifacts",
            "--volume", "runner_claude-home:/home/claude/.claude",
            # Work directory
            "--workdir", "/app/runner",
            # Image
            "swe-bench-worker:latest",
            # Command - run worker module with instance
            "python3.11", "-m", "worker",
            "--instance", json.dumps(instance),
            "--iterations", str(self.max_iterations),
            "--timeout", str(self.timeout_per_iteration)
        ]
        
        if not self.with_mcp:
            cmd.extend(["--no-mcp"])
        
        logger.info(f"Running worker in Docker for {instance['instance_id']}")
        
        try:
            # Run the Docker command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_per_iteration * self.max_iterations + 300  # Add buffer
            )
            
            if result.returncode == 0:
                # Parse JSON output from worker
                try:
                    output_lines = result.stdout.strip().split('\n')
                    # Find the JSON output (last line that starts with '{')
                    for line in reversed(output_lines):
                        if line.strip().startswith('{'):
                            return json.loads(line)
                    # Fallback
                    logger.error(f"No JSON output from Docker worker: {result.stdout}")
                    return {
                        "instance_id": instance['instance_id'],
                        "success": False,
                        "error": "No JSON output from worker",
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Docker output: {e}")
                    return {
                        "instance_id": instance['instance_id'],
                        "success": False,
                        "error": f"JSON parse error: {str(e)}",
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
            else:
                logger.error(f"Docker failed with code {result.returncode}: {result.stderr}")
                return {
                    "instance_id": instance['instance_id'],
                    "success": False,
                    "error": f"Docker exit code {result.returncode}",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"Docker timeout for {instance['instance_id']}")
            return {
                "instance_id": instance['instance_id'],
                "success": False,
                "error": "Docker timeout"
            }
        except Exception as e:
            logger.error(f"Docker exception: {e}")
            return {
                "instance_id": instance['instance_id'],
                "success": False,
                "error": str(e)
            }


def main():
    """CLI interface for the dispatcher."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run SWE-Bench tasks")
    parser.add_argument("--workers", "-j", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--sample", "-n", type=int, help="Number of instances to process")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--no-mcp", action="store_true", help="Run without MCP tools")
    parser.add_argument("--iterations", type=int, default=5, help="Max iterations per task")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout per iteration (seconds)")
    parser.add_argument("--run-name", help="Custom run name")
    parser.add_argument("--cache-dir", type=Path, help="Cache directory for git mirrors")
    parser.add_argument("--output-dir", type=Path, help="Output directory for results")
    parser.add_argument("--docker", action="store_true", help="Run workers in Docker containers")
    
    args = parser.parse_args()
    
    # Load instances
    instances = load_instances()
    
    # Apply sampling
    if args.sample:
        instances = instances[args.start:args.start + args.sample]
    else:
        instances = instances[args.start:]
    
    # Create dispatcher
    dispatcher = Dispatcher(
        max_workers=args.workers,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        with_mcp=not args.no_mcp,
        max_iterations=args.iterations,
        timeout_per_iteration=args.timeout,
        use_docker=args.docker
    )
    
    # Run
    run_name = dispatcher.run(instances, args.run_name)
    
    print(f"\n✅ Run complete: {run_name}")
    print(f"Results saved to: {dispatcher.output_dir / run_name}")


if __name__ == "__main__":
    main()