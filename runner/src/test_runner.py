"""Test runner for SWE-Bench repositories using pytest."""

import subprocess
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TestReport:
    """Results from running tests."""
    success: bool
    total_tests: int
    passed: int
    failed: int
    errors: int
    failures: List[Dict[str, str]]  # List of {test_name, error_message, file_path}
    stdout: str
    stderr: str
    duration: float
    
    def all_pass(self) -> bool:
        """Check if all tests passed."""
        return self.failed == 0 and self.errors == 0


def parse_pytest_output(output: str) -> Dict[str, Any]:
    """Parse pytest output to extract test results."""
    
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    summary_pattern = r'=+ (.*?) =+'
    summary_match = re.search(summary_pattern, output)
    
    stats = {
        'failed': 0,
        'passed': 0,
        'errors': 0,
        'total': 0
    }
    
    if summary_match:
        summary = summary_match.group(1)
        
        # Extract counts
        failed_match = re.search(r'(\d+) failed', summary)
        if failed_match:
            stats['failed'] = int(failed_match.group(1))
            
        passed_match = re.search(r'(\d+) passed', summary)
        if passed_match:
            stats['passed'] = int(passed_match.group(1))
            
        error_match = re.search(r'(\d+) error', summary)
        if error_match:
            stats['errors'] = int(error_match.group(1))
    
    stats['total'] = stats['failed'] + stats['passed'] + stats['errors']
    
    # Extract failure details
    failures = []
    
    # Pattern for FAILED test lines
    failed_pattern = r'^FAILED (.*?)(?:\s+-\s+(.*))?$'
    for line in output.split('\n'):
        match = re.match(failed_pattern, line)
        if match:
            test_name = match.group(1)
            error_msg = match.group(2) if match.group(2) else "Unknown error"
            
            # Try to extract file path from test name
            file_path = ""
            if '::' in test_name:
                parts = test_name.split('::')
                file_path = parts[0]
            
            failures.append({
                'test_name': test_name,
                'error_message': error_msg,
                'file_path': file_path
            })
    
    return {
        'stats': stats,
        'failures': failures
    }


def discover_failing_modules(failures: List[Dict[str, str]]) -> List[str]:
    """Extract unique module paths from test failures."""
    
    modules = set()
    
    for failure in failures:
        file_path = failure.get('file_path', '')
        if file_path and file_path.endswith('.py'):
            # Convert test file to source file
            # e.g., tests/test_foo.py -> foo.py
            if 'test_' in file_path:
                source_file = file_path.replace('test_', '').replace('tests/', '')
                modules.add(source_file)
            modules.add(file_path)
    
    return sorted(list(modules))


def run_tests(
    workdir: str,
    test_paths: Optional[List[str]] = None,
    timeout: int = 300,
    verbose: bool = True,
    pytest_cmd: str = 'pytest'
) -> TestReport:
    """Run pytest in the given directory and return parsed results."""
    
    import time
    start_time = time.time()
    
    # Check if this is a Django project
    manage_py = Path(workdir) / 'manage.py'
    if manage_py.exists():
        logger.info("Detected Django project, using Django test runner")
        return run_django_tests(workdir, test_paths, timeout)
    
    # Build pytest command
    cmd = [pytest_cmd]
    
    if verbose:
        cmd.append('-v')
    
    # Add coverage if needed
    cmd.extend(['--tb=short', '--no-header'])
    
    # Add specific test paths if provided
    if test_paths:
        cmd.extend(test_paths)
    
    logger.info(f"Running tests in {workdir}: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        duration = time.time() - start_time
        output = result.stdout + "\n" + result.stderr
        
        # Parse the output
        parsed = parse_pytest_output(output)
        
        return TestReport(
            success=(result.returncode == 0),
            total_tests=parsed['stats']['total'],
            passed=parsed['stats']['passed'],
            failed=parsed['stats']['failed'],
            errors=parsed['stats']['errors'],
            failures=parsed['failures'],
            stdout=result.stdout,
            stderr=result.stderr,
            duration=duration
        )
        
    except subprocess.TimeoutExpired:
        logger.error(f"Test timeout after {timeout}s")
        return TestReport(
            success=False,
            total_tests=0,
            passed=0,
            failed=0,
            errors=1,
            failures=[{
                'test_name': 'timeout',
                'error_message': f'Tests timed out after {timeout}s',
                'file_path': ''
            }],
            stdout='',
            stderr=f'Timeout after {timeout}s',
            duration=timeout
        )
    except Exception as e:
        logger.error(f"Test exception: {e}")
        return TestReport(
            success=False,
            total_tests=0,
            passed=0,
            failed=0,
            errors=1,
            failures=[{
                'test_name': 'exception',
                'error_message': str(e),
                'file_path': ''
            }],
            stdout='',
            stderr=str(e),
            duration=time.time() - start_time
        )


def filter_relevant_tests(workdir: str, issue_text: str) -> List[str]:
    """Try to identify relevant test files based on the issue description."""
    
    # Simple heuristic: look for test files mentioned in the issue
    test_files = []
    
    # Look for explicit test file mentions
    test_pattern = r'test[s]?[/_][\w/]+\.py'
    matches = re.findall(test_pattern, issue_text)
    test_files.extend(matches)
    
    # Look for module names and try to find corresponding tests
    # This is a simple heuristic and can be improved
    
    return test_files if test_files else None


def run_django_tests(
    workdir: str,
    test_paths: Optional[List[str]] = None,
    timeout: int = 300
) -> TestReport:
    """Run Django's manage.py test."""
    import time
    start_time = time.time()
    
    cmd = ['python', 'manage.py', 'test', '--verbosity=2']
    if test_paths:
        cmd.extend(test_paths)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Parse Django test output
        output = result.stdout + "\n" + result.stderr
        
        # Django shows: "Ran X tests in Ys"
        ran_match = re.search(r'Ran (\d+) tests? in', output)
        total_tests = int(ran_match.group(1)) if ran_match else 0
        
        # Django shows: "FAILED (failures=X, errors=Y)"
        failed_match = re.search(r'FAILED.*failures=(\d+)', output)
        errors_match = re.search(r'FAILED.*errors=(\d+)', output)
        
        failed = int(failed_match.group(1)) if failed_match else 0
        errors = int(errors_match.group(1)) if errors_match else 0
        passed = total_tests - failed - errors
        
        return TestReport(
            success=(result.returncode == 0),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            errors=errors,
            failures=[],  # Django doesn't give structured failure info
            stdout=result.stdout,
            stderr=result.stderr,
            duration=time.time() - start_time
        )
    except Exception as e:
        return TestReport(
            success=False,
            total_tests=0,
            passed=0,
            failed=0,
            errors=1,
            failures=[{'test_name': 'exception', 'error_message': str(e), 'file_path': ''}],
            stdout='',
            stderr=str(e),
            duration=time.time() - start_time
        )