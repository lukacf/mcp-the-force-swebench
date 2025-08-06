"""Worker module for processing individual SWE-Bench tasks."""

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from . import git_utils
    from . import test_runner
    from . import claude_force_client
    from . import patch_utils
except ImportError:
    # For direct execution
    import git_utils
    import test_runner
    import claude_force_client
    import patch_utils

logger = logging.getLogger(__name__)


class Worker:
    """Handles the execution of a single SWE-Bench task."""
    
    def __init__(
        self,
        cache_dir: Path = None,
        work_dir: Path = None,
        max_iterations: int = 5,
        timeout_per_iteration: int = 600,
        with_mcp: bool = True
    ):
        self.cache_dir = cache_dir or Path("runner/artifacts/cache")
        self.work_dir = work_dir or Path("runner/artifacts/worktrees")
        self.max_iterations = max_iterations
        self.timeout_per_iteration = timeout_per_iteration
        self.with_mcp = with_mcp
        
    def solve_task(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Solve a single SWE-Bench task with local test iteration."""
        
        instance_id = instance['instance_id']
        start_time = time.time()
        
        logger.info(f"Starting task: {instance_id}")
        
        # Extract GitHub URL from repo field (e.g., "django/django" -> full URL)
        repo = instance['repo']
        if not repo.startswith('http'):
            repo_url = f"https://github.com/{repo}"
        else:
            repo_url = repo
            
        commit_hash = instance.get('base_commit', 'HEAD')
        
        try:
            # Use worktree context manager
            with git_utils.checkout_worktree(repo_url, commit_hash, self.cache_dir, self.work_dir) as workdir:
                logger.info(f"Checked out {instance_id} at {commit_hash} in {workdir}")
                
                # Step 1: Set up Python environment
                logger.info("Setting up Python environment...")
                venv_path = workdir / '.venv'
                
                # Check for cached venv first
                venv_cache_dir = Path("runner/artifacts/venvs")
                cached_venv = venv_cache_dir / repo.replace("/", "_") / commit_hash
                
                if cached_venv.exists() and not venv_path.exists():
                    # Use hard-linked copy for speed
                    logger.info(f"Using cached venv from {cached_venv}")
                    try:
                        subprocess.run(
                            ['cp', '-al', str(cached_venv), str(venv_path)],
                            check=True,
                            capture_output=True
                        )
                        # Update activation for this location
                        activate_script = venv_path / 'bin' / 'activate'
                        if activate_script.exists():
                            # Fix VIRTUAL_ENV path in activate script
                            subprocess.run(
                                ['sed', '-i', '', f's|VIRTUAL_ENV=.*|VIRTUAL_ENV="{venv_path}"|', 
                                 str(activate_script)],
                                capture_output=True
                            )
                    except subprocess.CalledProcessError:
                        # Fallback to regular copy if hard links fail
                        shutil.copytree(cached_venv, venv_path, symlinks=True)
                
                if not venv_path.exists():
                    subprocess.run(
                        ['python3', '-m', 'venv', str(venv_path)],
                        check=True,
                        capture_output=True
                    )
                    
                    # Install the project and test dependencies
                    pip = venv_path / 'bin' / 'pip'
                    logger.info("Installing project dependencies...")
                    
                    # First upgrade pip
                    subprocess.run(
                        [str(pip), 'install', '--upgrade', 'pip'],
                        check=True,
                        capture_output=True
                    )
                    
                    # Try to install with test extras, fall back to regular install
                    try:
                        subprocess.run(
                            [str(pip), 'install', '--progress-bar', 'off', '-e', '.[test]'],
                            cwd=workdir,
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError:
                        # Fallback: try without test extras
                        subprocess.run(
                            [str(pip), 'install', '--progress-bar', 'off', '-e', '.'],
                            cwd=workdir,
                            check=True,
                            capture_output=True
                        )
                        # Install pytest separately
                        subprocess.run(
                            [str(pip), 'install', 'pytest'],
                            check=True,
                            capture_output=True
                        )
                
                # Use the venv's pytest
                pytest_path = venv_path / 'bin' / 'pytest'
                
                # Step 2: Run initial tests to see what's failing
                logger.info("Running initial tests to identify failures...")
                initial_report = test_runner.run_tests(str(workdir), pytest_cmd=str(pytest_path))
                
                if initial_report.all_pass():
                    logger.warning(f"All tests passed initially for {instance_id} - nothing to fix!")
                    return self._create_result(instance, success=False, 
                                             error="All tests passed initially", 
                                             duration=time.time() - start_time)
                
                logger.info(f"Initial test results: {initial_report.failed} failed, {initial_report.passed} passed")
                
                # Step 2: Get failing modules for context
                failing_modules = test_runner.discover_failing_modules(initial_report.failures)
                logger.info(f"Failing modules: {failing_modules}")
                
                # Step 3: Iteration loop
                best_patch = None
                best_report = initial_report
                
                for iteration in range(self.max_iterations):
                    logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
                    
                    # Format the task for Claude
                    if iteration == 0:
                        # First attempt - use the original problem statement
                        task = claude_force_client.format_swe_task(instance, self.with_mcp)
                        
                        # Add test failure information
                        if initial_report.failures:
                            task += f"\n\nFailing tests:\n"
                            for failure in initial_report.failures[:5]:  # Show first 5 failures
                                task += f"- {failure['test_name']}: {failure['error_message']}\n"
                    else:
                        # Subsequent attempts - provide feedback
                        task = f"""Previous patch attempt failed. Please try again.

Original issue:
{instance['problem_statement']}

Previous patch:
```diff
{best_patch}
```

Test results after patch:
Failed: {best_report.failed}, Passed: {best_report.passed}

Failing tests:
"""
                        for failure in best_report.failures[:5]:
                            task += f"- {failure['test_name']}: {failure['error_message']}\n"
                        
                        task += "\nPlease provide an updated patch that fixes these test failures."
                    
                    # Call Claude
                    claude_result = claude_force_client.call_claude(
                        task,
                        timeout=self.timeout_per_iteration,
                        run_id=f"swe-{instance_id}-{int(time.time())}",
                        instance_id=instance_id
                    )
                    
                    if not claude_result['success']:
                        logger.error(f"Claude failed: {claude_result.get('error')}")
                        continue
                    
                    # Extract patch from response
                    raw_patch = patch_utils.extract_diff_from_response(claude_result['response'])
                    if not raw_patch:
                        logger.warning("No patch found in Claude's response")
                        continue
                    
                    # Clean and validate patch
                    cleaned_patch = patch_utils.validate_and_clean_patch(raw_patch, instance_id)
                    if not cleaned_patch:
                        logger.warning("Patch validation failed")
                        continue
                    
                    # Apply patch
                    if patch_utils.apply_patch(str(workdir), cleaned_patch):
                        logger.info("Patch applied successfully")
                        
                        # Run tests again
                        new_report = test_runner.run_tests(str(workdir), pytest_cmd=str(pytest_path))
                        logger.info(f"Test results after patch: {new_report.failed} failed, {new_report.passed} passed")
                        
                        # Check if we've improved
                        if new_report.failed < best_report.failed or (new_report.failed == 0 and new_report.errors == 0):
                            best_patch = cleaned_patch
                            best_report = new_report
                            
                            if new_report.all_pass():
                                logger.info("All tests pass! Task solved.")
                                
                                # Extract summary if available
                                summary = patch_utils.extract_summary_from_response(claude_result['response'])
                                
                                return self._create_result(
                                    instance, 
                                    success=True,
                                    patch=best_patch,
                                    summary=summary,
                                    duration=time.time() - start_time,
                                    iterations=iteration + 1,
                                    test_report=new_report
                                )
                        
                        # Revert the patch if it didn't help
                        subprocess.run(['git', 'reset', '--hard'], cwd=workdir, capture_output=True)
                        subprocess.run(['git', 'clean', '-xfd'], cwd=workdir, capture_output=True)
                    else:
                        logger.error("Failed to apply patch")
                
                # If we get here, we didn't solve it completely
                logger.warning(f"Failed to fully solve {instance_id} after {self.max_iterations} iterations")
                
                return self._create_result(
                    instance,
                    success=False,
                    patch=best_patch,  # Return best attempt
                    error=f"Tests still failing after {self.max_iterations} iterations",
                    duration=time.time() - start_time,
                    iterations=self.max_iterations,
                    test_report=best_report
                )
                
        except Exception as e:
            logger.error(f"Exception solving {instance_id}: {e}")
            return self._create_result(
                instance,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def _create_result(
        self,
        instance: Dict[str, Any],
        success: bool,
        patch: str = None,
        summary: str = None,
        error: str = None,
        duration: float = 0,
        iterations: int = 0,
        test_report: Any = None
    ) -> Dict[str, Any]:
        """Create a standardized result dictionary."""
        
        result = {
            "instance_id": instance['instance_id'],
            "repo": instance['repo'],
            "base_commit": instance.get('base_commit', ''),
            "problem_statement": instance['problem_statement'],
            "success": success,
            "duration": duration,
            "iterations": iterations,
            "timestamp": datetime.now().isoformat(),
            "model": f"claude-force-{'with' if self.with_mcp else 'without'}-mcp"
        }
        
        if patch:
            result["prediction"] = patch
            
        if summary:
            result["problem_solving_summary"] = summary
            
        if error:
            result["error"] = error
            
        if test_report:
            result["final_test_results"] = {
                "passed": test_report.passed,
                "failed": test_report.failed,
                "errors": test_report.errors,
                "total": test_report.total_tests
            }
            
        return result


def main():
    """CLI interface for running a single worker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run a single SWE-Bench task")
    parser.add_argument("--instance", required=True, help="JSON string of instance data")
    parser.add_argument("--cache-dir", type=Path, help="Cache directory")
    parser.add_argument("--work-dir", type=Path, help="Work directory")
    parser.add_argument("--no-mcp", action="store_true", help="Run without MCP")
    parser.add_argument("--iterations", type=int, default=5, help="Max iterations")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout per iteration")
    
    args = parser.parse_args()
    
    # Parse instance
    instance = json.loads(args.instance)
    
    # Create worker
    worker = Worker(
        cache_dir=args.cache_dir,
        work_dir=args.work_dir,
        max_iterations=args.iterations,
        timeout_per_iteration=args.timeout,
        with_mcp=not args.no_mcp
    )
    
    # Run task
    result = worker.solve_task(instance)
    
    # Output result as JSON for the dispatcher to parse
    print(json.dumps(result))
    
    # Exit with appropriate code
    sys.exit(0 if result.get('success', False) else 1)


if __name__ == "__main__":
    import sys
    main()