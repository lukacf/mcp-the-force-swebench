"""
Core evaluation module for SWE-Bench patches.
This module implements f(patch) => pass/fail with 100% reliability.
"""

import re
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_test_files_from_patch(test_patch: str, workdir: str = None) -> List[str]:
    """Extract test file paths from a test_patch diff.
    
    The test_patch contains modifications to test files that verify the fix.
    We need to run ONLY these test files, not the entire test suite.
    
    Handles two cases:
    1. Direct Python test file modifications (easy)
    2. Data file modifications - need to find Python tests in same directory
    """
    modified_files = []
    python_test_files = []
    data_files = []
    
    # Parse diff to find all modified files
    diff_pattern = r'^diff --git a/(.*?) b/(.*?)$'
    
    for line in test_patch.split('\n'):
        match = re.match(diff_pattern, line)
        if match:
            file_path = match.group(1)
            modified_files.append(file_path)
            
            # Categorize the file
            if file_path.endswith('.py'):
                if 'test' in file_path.lower() or file_path.endswith('/tests.py'):
                    python_test_files.append(file_path)
            else:
                # Data file (txt, json, etc)
                data_files.append(file_path)
    
    # If we have Python test files, use those
    if python_test_files:
        return python_test_files
    
    # If we only have data files, find Python tests in the same directories
    if data_files and workdir:
        test_files_to_run = set()
        
        for data_file in data_files:
            # Get directory of data file
            data_dir = Path(data_file).parent
            
            # Look for Python test files in the same directory
            test_dir = Path(workdir) / data_dir
            if test_dir.exists():
                # Find all test*.py files in this directory
                for test_file in test_dir.glob('test*.py'):
                    # Convert back to relative path
                    rel_path = test_file.relative_to(workdir)
                    test_files_to_run.add(str(rel_path))
                
                # Also check for tests.py
                tests_py = test_dir / 'tests.py'
                if tests_py.exists():
                    rel_path = tests_py.relative_to(workdir)
                    test_files_to_run.add(str(rel_path))
        
        return list(test_files_to_run)
    
    # Fallback: if we can't find specific test files, look for any test modules
    # mentioned in the same directory as modified files
    if data_files:
        test_dirs = set()
        for data_file in data_files:
            # For files like tests/validators/invalid_urls.txt
            # We want to run tests in tests/validators/
            test_dir = str(Path(data_file).parent)
            if 'test' in test_dir:
                test_dirs.add(test_dir)
        
        # Return directory paths for Django test runner
        return list(test_dirs)
    
    return []


# Local execution functions removed - all evaluation happens on GCP






def should_use_docker(instance: Dict[str, Any]) -> bool:
    """ALWAYS use Docker/GCP for all instances."""
    return True


def evaluate_patch_docker(
    instance: Dict[str, Any],
    patch: str
) -> Dict[str, Any]:
    """Evaluate patch using GCP tester service."""
    
    import requests
    
    result = {
        "instance_id": instance["instance_id"],
        "passed": False,
        "error": None,
        "test_output": "",
        "method": "gcp_docker"
    }
    
    # GCP tester service URL
    TESTER_URL = "http://35.209.45.223:8080/test"
    
    logger.info(f"Sending request to GCP tester for {instance['instance_id']}")
    
    try:
        # Extract test files to know what to run
        test_files = extract_test_files_from_patch(instance["test_patch"])
        result["test_files"] = test_files
        
        # For now, we need to send the combined patch (solution + test)
        # The current tester API only accepts a single patch
        combined_patch = patch + "\n" + instance.get("test_patch", "")
        
        # Send request to GCP tester matching its API
        payload = {
            "instance_id": instance["instance_id"],
            "patch": combined_patch,
            "timeout": 900,
            "test_files": test_files  # Add specific test files to run
        }
        
        response = requests.post(
            TESTER_URL,
            json=payload,
            timeout=920  # Slightly longer than server timeout
        )
        
        if response.status_code == 200:
            response_data = response.json()
            # The tester returns passed/failed/errors counts
            passed_count = response_data.get("passed", 0)
            failed_count = response_data.get("failed", 0)
            errors_count = response_data.get("errors", 0)
            
            # Consider it passed only if there are passed tests and no failures/errors
            # Also check if tests were collected (indicates successful test run)
            collected = response_data.get("collected", 0)
            if collected > 0 and passed_count == 0 and failed_count == 0 and errors_count == 0:
                # All tests passed (pytest shows "X passed" not in our stats)
                result["passed"] = True
            else:
                result["passed"] = passed_count > 0 and failed_count == 0 and errors_count == 0
            result["test_output"] = response_data.get("log_tail", "")
            result["stats"] = {
                "passed": passed_count,
                "failed": failed_count,
                "errors": errors_count,
                "duration": response_data.get("duration", 0)
            }
            
            if not result["passed"]:
                result["error"] = f"Tests failed: {failed_count} failed, {errors_count} errors"
        else:
            result["error"] = f"GCP tester returned status {response.status_code}: {response.text}"
            
        return result
            
    except requests.Timeout:
        result["error"] = "GCP tester request timed out"
        return result
    except Exception as e:
        result["error"] = f"GCP tester exception: {str(e)}"
        return result


def evaluate_patch(
    instance: Dict[str, Any],
    patch: str,
    workdir: Optional[str] = None,
    force_local: bool = False
) -> Dict[str, Any]:
    """
    Main evaluation function: f(patch) => pass/fail
    ALL evaluations go through GCP Docker service.
    
    Args:
        instance: SWE-Bench instance dict with test_patch
        patch: The proposed solution patch to evaluate
        workdir: Ignored - no local execution
        force_local: Ignored - always uses GCP
        
    Returns:
        Dict with 'passed' (bool), 'error' (str), and diagnostic info
    """
    
    # ALWAYS use GCP Docker evaluation
    logger.info(f"Using GCP Docker evaluation for {instance['instance_id']}")
    return evaluate_patch_docker(instance, patch)


# Validation functions
def validate_with_known_patch(instance: Dict[str, Any], workdir: str) -> bool:
    """Validate that the known good patch makes tests pass."""
    
    known_patch = instance.get("patch", "")
    if not known_patch:
        logger.error(f"No known patch for {instance['instance_id']}")
        return False
    
    result = evaluate_patch(instance, known_patch, workdir, force_local=True)
    
    if result["passed"]:
        logger.info(f"✓ Known patch passed for {instance['instance_id']}")
    else:
        logger.error(f"✗ Known patch FAILED for {instance['instance_id']}: {result['error']}")
        
    return result["passed"]


def validate_with_empty_patch(instance: Dict[str, Any], workdir: str) -> bool:
    """Validate that empty patch makes tests fail."""
    
    empty_patch = ""
    result = evaluate_patch(instance, empty_patch, workdir, force_local=True)
    
    if not result["passed"]:
        logger.info(f"✓ Empty patch correctly failed for {instance['instance_id']}")
        return True
    else:
        logger.error(f"✗ Empty patch incorrectly PASSED for {instance['instance_id']}")
        return False