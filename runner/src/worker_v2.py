"""Worker module for processing individual SWE-Bench tasks using the new evaluator."""

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
    from . import evaluator
    from . import claude_force_client
    from . import patch_utils
except ImportError:
    # For direct execution
    import git_utils
    import evaluator
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
        """Solve a single SWE-Bench task using the new evaluator."""
        
        instance_id = instance['instance_id']
        start_time = time.time()
        
        logger.info(f"Starting task: {instance_id}")
        
        # Create Claude Force client
        claude_client = claude_force_client.ClaudeForceClient(
            with_mcp=self.with_mcp,
            cache_dir=self.cache_dir
        )
        
        try:
            # Check if this is a complex repo that needs Docker
            if evaluator.should_use_docker(instance):
                logger.info(f"Using Docker evaluation for {instance_id}")
                return self._solve_with_docker(instance, claude_client, start_time)
            else:
                return self._solve_with_local(instance, claude_client, start_time)
                
        except Exception as e:
            logger.error(f"Task failed: {e}", exc_info=True)
            return self._create_result(
                instance,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
        finally:
            claude_client.cleanup()
    
    def _solve_with_local(self, instance: Dict[str, Any], claude_client, start_time: float) -> Dict[str, Any]:
        """Solve task using local evaluation."""
        
        instance_id = instance['instance_id']
        repo_url = f"https://github.com/{instance['repo']}"
        base_commit = instance['base_commit']
        
        # Use checkout_worktree context manager
        with git_utils.checkout_worktree(repo_url, base_commit, self.cache_dir, self.work_dir) as workdir:
            logger.info(f"Working in: {workdir}")
            
            # Set up the repository  
            self._setup_repository(workdir, instance)
            
            # Step 1: Get Claude to understand the problem and generate patch
            best_patch = None
            best_passed = False
            
            for iteration in range(self.max_iterations):
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
                
                # Let Claude analyze the problem
                logger.info("Getting Claude to analyze the problem...")
                claude_result = claude_client.analyze_and_fix_issue(
                    instance=instance,
                    workdir=str(workdir),
                    previous_patch=best_patch,
                    timeout=self.timeout_per_iteration,
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
                
                # Evaluate the patch using our new evaluator
                logger.info("Evaluating patch...")
                eval_result = evaluator.evaluate_patch(
                    instance, 
                    cleaned_patch, 
                    str(workdir),
                    force_local=True
                )
                
                if eval_result['passed']:
                    logger.info("✅ Tests pass! Task solved.")
                    best_patch = cleaned_patch
                    best_passed = True
                    
                    # Extract summary if available
                    summary = patch_utils.extract_summary_from_response(claude_result['response'])
                    
                    return self._create_result(
                        instance, 
                        success=True,
                        patch=best_patch,
                        summary=summary,
                        duration=time.time() - start_time,
                        iterations=iteration + 1,
                        test_output=eval_result.get('test_output', '')
                    )
                else:
                    logger.info(f"❌ Tests failed: {eval_result.get('error', 'Unknown error')}")
                    # Store this patch if it's the first attempt
                    if best_patch is None:
                        best_patch = cleaned_patch
            
            # Max iterations reached
            return self._create_result(
                instance,
                success=False,
                patch=best_patch,
                error="Max iterations reached without solving the task",
                duration=time.time() - start_time,
                iterations=self.max_iterations
            )
    
    def _solve_with_docker(self, instance: Dict[str, Any], claude_client, start_time: float) -> Dict[str, Any]:
        """Solve task using Docker evaluation."""
        
        instance_id = instance['instance_id']
        
        # For Docker evaluation, we don't need a local worktree
        # Just get Claude to analyze and generate patches
        best_patch = None
        best_passed = False
        
        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # Let Claude analyze the problem (without local workdir)
            logger.info("Getting Claude to analyze the problem...")
            claude_result = claude_client.analyze_and_fix_issue(
                instance=instance,
                workdir=None,  # No local workdir for Docker
                previous_patch=best_patch,
                timeout=self.timeout_per_iteration,
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
            
            # Evaluate the patch using Docker
            logger.info("Evaluating patch with Docker...")
            eval_result = evaluator.evaluate_patch_docker(instance, cleaned_patch)
            
            if eval_result['passed']:
                logger.info("✅ Tests pass! Task solved.")
                best_patch = cleaned_patch
                best_passed = True
                
                # Extract summary if available
                summary = patch_utils.extract_summary_from_response(claude_result['response'])
                
                return self._create_result(
                    instance, 
                    success=True,
                    patch=best_patch,
                    summary=summary,
                    duration=time.time() - start_time,
                    iterations=iteration + 1,
                    test_output=eval_result.get('test_output', '')
                )
            else:
                logger.info(f"❌ Tests failed: {eval_result.get('error', 'Unknown error')}")
                # Store this patch if it's the first attempt
                if best_patch is None:
                    best_patch = cleaned_patch
        
        # Max iterations reached
        return self._create_result(
            instance,
            success=False,
            patch=best_patch,
            error="Max iterations reached without solving the task",
            duration=time.time() - start_time,
            iterations=self.max_iterations
        )
    
    def _setup_repository(self, workdir: Path, instance: Dict[str, Any]) -> None:
        """Set up the repository (install dependencies, etc)."""
        
        # Install dependencies based on project type
        if (workdir / 'setup.py').exists() or (workdir / 'pyproject.toml').exists():
            logger.info("Setting up Python project...")
            
            # Create virtual environment
            venv_path = workdir / '.venv'
            if not venv_path.exists():
                subprocess.run(['python', '-m', 'venv', str(venv_path)], cwd=workdir, check=True)
            
            # Install in development mode
            pip_path = venv_path / 'bin' / 'pip'
            if (workdir / 'setup.py').exists():
                subprocess.run([str(pip_path), 'install', '-e', '.', '-q'], cwd=workdir)
            elif (workdir / 'pyproject.toml').exists():
                subprocess.run([str(pip_path), 'install', '-e', '.', '-q'], cwd=workdir)
            
            # Install test dependencies
            subprocess.run([str(pip_path), 'install', 'pytest', '-q'], cwd=workdir)
    
    def _create_result(
        self, 
        instance: Dict[str, Any],
        success: bool,
        patch: Optional[str] = None,
        summary: Optional[str] = None,
        error: Optional[str] = None,
        duration: float = 0,
        iterations: int = 0,
        test_output: str = ""
    ) -> Dict[str, Any]:
        """Create a standardized result dictionary."""
        
        return {
            "instance_id": instance['instance_id'],
            "repo": instance['repo'],
            "base_commit": instance['base_commit'],
            "success": success,
            "patch": patch,
            "summary": summary,
            "error": error,
            "duration": duration,
            "iterations": iterations,
            "test_output": test_output,
            "timestamp": datetime.utcnow().isoformat()
        }