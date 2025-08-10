"""
FastAPI micro-service v2: POST /test {instance_id, patch, timeout, test_files}
Runs specific tests inside the relevant Epoch SWE-Bench image and returns JSON stats.
FIXED VERSION: Uses python -m pytest to ensure correct interpreter
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import subprocess, tempfile, os, uuid, time, json, re, shutil, textwrap
import logging

SCRATCH = "/scratch/repos"          # bind-mount host SSD here
os.makedirs(SCRATCH, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="swe-tester-v2", version="2.0.0")


class Request(BaseModel):
    instance_id: str = Field(..., description="SWE-Bench instance ID, e.g. django__django-16595")
    patch:       str
    timeout:     int = 900
    test_files:  Optional[List[str]] = Field(None, description="Specific test files to run")


def verify_python_version(container_name: str, repo_name: str) -> tuple:
    """Verify Python version in the testbed environment."""
    cmd = ["docker", "exec", container_name,
           "conda", "run", "-n", "testbed",
           "python", "-c", 
           "import sys, platform; print(sys.executable); print(platform.python_version())"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        executable = lines[0] if len(lines) > 0 else "unknown"
        version = lines[1] if len(lines) > 1 else "unknown"
        logger.info(f"Python version for {repo_name}: {version} at {executable}")
        
        # Warn if using Python 3.10+ for psf/requests
        if repo_name == "psf" and version.startswith(('3.10', '3.11', '3.12')):
            logger.warning(f"WARNING: psf/requests using Python {version}, expected <=3.9")
        
        return executable, version
    return "unknown", "unknown"


@app.post("/test")
def run_test(r: Request):
    t0 = time.time()

    # Epoch AI images use instance_id format
    image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{r.instance_id}:latest"
    
    # lazy-pull (ignore failure – image may already exist locally)
    subprocess.run(["docker", "pull", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cname = f"swe-{uuid.uuid4().hex[:8]}"
    workdir = f"/workspace"
    # Use instance_id as directory name to avoid collisions
    host_repo_dir = os.path.join(SCRATCH, r.instance_id)
    os.makedirs(host_repo_dir, exist_ok=True)

    try:
        # 1. start container (detached)
        # Note: Epoch AI images already have the repo checked out at the correct commit
        subprocess.run([
            "docker", "run", "-d", "--name", cname,
            "-v", f"{host_repo_dir}:{workdir}/scratch",
            "-w", workdir,
            image, "sleep", "infinity"
        ], check=True, stdout=subprocess.DEVNULL)

        # 2. Find the repo directory inside the container
        # Epoch AI images typically have the repo in /testbed or similar
        find_repo = subprocess.run(
            f"docker exec {cname} find / -maxdepth 3 -name .git -type d 2>/dev/null | head -1 | xargs dirname",
            shell=True, text=True, capture_output=True
        )
        repo_dir = find_repo.stdout.strip() or "/testbed"

        # 2.5. Verify Python version
        repo_name = r.instance_id.split("__")[0].split("/")[-1]
        verify_python_version(cname, repo_name)

        # 3. apply patch (skip if empty)
        if r.patch and r.patch.strip():
            proc = subprocess.run(
                ["docker", "exec", "-i", cname, "git", "-C", repo_dir, "apply", "-"],
                input=r.patch.encode(),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if proc.returncode != 0:
                raise HTTPException(422, f"Patch failed:\n{proc.stderr.decode()[:400]}")

        # 4. Determine repo type and run appropriate tests
        repo_name = r.instance_id.split("__")[0]
        is_django = repo_name == "django"
        
        logger.info(f"Running tests for {r.instance_id} (django={is_django})")
        
        if is_django:
            test_result = run_django_tests_with_retry(cname, repo_dir, r.test_files, r.timeout)
        else:
            test_result = run_pytest_tests(cname, repo_dir, r.test_files, r.timeout)
        
        out = test_result.stdout + "\n" + test_result.stderr
        
        # Parse results based on test runner
        if is_django:
            stats = _parse_django_output(out)
        else:
            stats = _parse_pytest(out)
        
        tail = "\n".join(out.splitlines()[-50:])  # Last 50 lines for better debugging

        return {
            **stats,
            "duration": round(time.time() - t0, 2),
            "log_tail": tail,
            "test_files_run": r.test_files or ["all"]
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Test execution timed-out")

    finally:
        subprocess.run(["docker", "rm", "-f", cname],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_pytest_installed(container_name: str):
    """Ensure pytest is installed in the testbed conda environment."""
    # Check if pytest exists IN THE CONDA ENV
    check_cmd = ["docker", "exec", container_name, 
                 "conda", "run", "-n", "testbed", "python", "-c", "import pytest; print(pytest.__file__)"]
    check_result = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if check_result.returncode != 0:
        # pytest not found, install it
        logger.info("pytest not found in testbed env, installing...")
        install_cmd = ["docker", "exec", container_name,
                       "conda", "run", "-n", "testbed", "pip", "install", "pytest<7"]
        install_result = subprocess.run(install_cmd, capture_output=True, text=True)
        if install_result.returncode != 0:
            logger.error(f"Failed to install pytest: {install_result.stderr}")
            return False
        logger.info("pytest installed successfully")
    else:
        # Verify pytest is from the conda env
        pytest_path = check_result.stdout.strip()
        if "/envs/testbed/" not in pytest_path:
            logger.warning(f"pytest found outside conda env: {pytest_path}, reinstalling...")
            install_cmd = ["docker", "exec", container_name,
                           "conda", "run", "-n", "testbed", "pip", "install", "--force-reinstall", "pytest<7"]
            subprocess.run(install_cmd, capture_output=True, text=True)
    return True

def ensure_django_test_dependencies(container_name: str, repo_dir: str):
    """Ensure Django test dependencies are installed."""
    logger.info("Ensuring Django test dependencies are installed...")
    
    # First, check if there's a test requirements file
    requirements_files = [
        f"{repo_dir}/tests/requirements/py3.txt",
        f"{repo_dir}/tests/requirements/tests.txt",
        f"{repo_dir}/tests/requirements.txt",
        f"{repo_dir}/test-requirements.txt",
        f"{repo_dir}/requirements-test.txt"
    ]
    
    installed_from_file = False
    for req_file in requirements_files:
        check_cmd = ["docker", "exec", container_name, "test", "-f", req_file]
        if subprocess.run(check_cmd, capture_output=True).returncode == 0:
            logger.info(f"Found requirements file: {req_file}")
            install_cmd = ["docker", "exec", container_name,
                          "conda", "run", "-n", "testbed", "pip", "install", "-r", req_file]
            install_result = subprocess.run(install_cmd, capture_output=True, text=True)
            if install_result.returncode == 0:
                logger.info(f"Installed dependencies from {req_file}")
                installed_from_file = True
                break
            else:
                logger.warning(f"Failed to install from {req_file}: {install_result.stderr}")
    
    # If no requirements file, install common Django test dependencies
    if not installed_from_file:
        # Common dependencies needed for Django test suite
        common_deps = ["pytz", "jinja2", "numpy", "Pillow", "PyYAML", "sqlparse"]
        logger.info("No requirements file found, installing common Django test dependencies...")
        
        for dep in common_deps:
            install_cmd = ["docker", "exec", container_name,
                          "conda", "run", "-n", "testbed", "pip", "install", dep]
            result = subprocess.run(install_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.debug(f"Installed {dep}")
            else:
                # Some deps might fail, that's OK
                logger.debug(f"Could not install {dep} (may not be needed): {result.stderr}")
    
    # Special handling for specific Django versions that need additional setup
    # Check Django version to apply version-specific fixes
    version_cmd = ["docker", "exec", container_name,
                   "conda", "run", "-n", "testbed", 
                   "python", "-c", "import django; print(django.VERSION[:2])"]
    version_result = subprocess.run(version_cmd, capture_output=True, text=True)
    if version_result.returncode == 0:
        try:
            major, minor = eval(version_result.stdout.strip())
            logger.info(f"Django version: {major}.{minor}")
            
            # Django 3.2+ might need additional deps
            if major >= 3 and minor >= 2:
                extra_deps = ["asgiref>=3.3.2", "backports.zoneinfo;python_version<'3.9'"]
                for dep in extra_deps:
                    install_cmd = ["docker", "exec", container_name,
                                  "conda", "run", "-n", "testbed", "pip", "install", dep]
                    subprocess.run(install_cmd, capture_output=True, text=True)
        except:
            pass  # If version detection fails, continue anyway

def install_missing_module(container_name: str, module_name: str) -> bool:
    """Try to install a missing Python module."""
    # Common module name to package name mappings
    module_to_package = {
        'pytz': 'pytz',
        'jinja2': 'jinja2',
        'PIL': 'Pillow',
        'yaml': 'PyYAML',
        'numpy': 'numpy',
        'sqlparse': 'sqlparse',
        'asgiref': 'asgiref',
        'backports': 'backports.zoneinfo'
    }
    
    package_name = module_to_package.get(module_name, module_name)
    logger.info(f"Attempting to install missing module: {module_name} (package: {package_name})")
    
    install_cmd = ["docker", "exec", container_name,
                   "conda", "run", "-n", "testbed", "pip", "install", package_name]
    result = subprocess.run(install_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info(f"Successfully installed {package_name}")
        return True
    else:
        logger.error(f"Failed to install {package_name}: {result.stderr}")
        return False

def run_pytest_tests(container_name: str, repo_dir: str, test_files: Optional[List[str]], timeout: int):
    """Run pytest with specific test files or all tests."""
    
    # Ensure pytest is installed
    ensure_pytest_installed(container_name)
    
    # Set environment to avoid user site pollution
    env_vars = "PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1"
    
    # CRITICAL FIX: Use python -m pytest instead of pytest directly
    cmd = ["docker", "exec", "-w", repo_dir, container_name, 
           "bash", "-c", f"{env_vars} conda run -n testbed python -m pytest"]
    
    if test_files:
        # Run only specific test files
        # FIXED: Removed --no-header flag that causes failures
        pytest_args = "-v --tb=short -rN " + " ".join(test_files)
        cmd[-1] += f" {pytest_args}"
        logger.info(f"Running specific tests: {test_files}")
    else:
        # Fallback to running all tests (existing behavior)
        cmd[-1] += " -xvs"
        logger.info("Running all tests (no specific files provided)")
    
    return subprocess.run(
        cmd,
        capture_output=True, 
        text=True, 
        timeout=timeout
    )


def run_django_tests_with_retry(container_name: str, repo_dir: str, test_files: Optional[List[str]], timeout: int):
    """Run Django tests with automatic retry on import errors."""
    # First attempt
    result = run_django_tests(container_name, repo_dir, test_files, timeout)
    
    # Check if failed due to import error
    error_text = result.stderr + result.stdout
    import_error_match = re.search(r"ModuleNotFoundError: No module named '(\w+)'", error_text)
    
    if import_error_match and result.returncode != 0:
        missing_module = import_error_match.group(1)
        logger.info(f"Test failed due to missing module: {missing_module}")
        
        # Try to install the missing module
        if install_missing_module(container_name, missing_module):
            logger.info("Retrying tests after installing missing module...")
            # Retry the tests
            result = run_django_tests(container_name, repo_dir, test_files, timeout)
    
    # Check for Django app registry errors
    if result.returncode != 0 and test_files:
        app_error_match = re.search(
            r"(?:ModuleNotFoundError:|ImportError:|django\.core\.exceptions\.ImproperlyConfigured:).*?(?:No module named|Could not import) '?([\w\.]+)'?",
            error_text
        )
        
        if app_error_match:
            failed_module = app_error_match.group(1)
            logger.warning(f"Django app import error: {failed_module}")
            
            # Try converting test labels if they look like file paths
            if any('/' in tf or tf.endswith('.py') for tf in test_files):
                # Convert file paths to Django test labels
                new_test_files = []
                for tf in test_files:
                    # Remove .py extension
                    if tf.endswith('.py'):
                        tf = tf[:-3]
                    # Convert path separators to dots
                    tf = tf.replace('/', '.')
                    # Remove 'tests.' prefix if present
                    if tf.startswith('tests.'):
                        tf = tf[6:]
                    # For Django core tests, the format is just app_name.TestClass.test_method
                    # Extract just the app name if it's a full path
                    parts = tf.split('.')
                    if len(parts) > 1 and parts[0] in ['admin', 'auth', 'contenttypes', 'sessions', 
                                                         'messages', 'staticfiles', 'forms', 'db',
                                                         'http', 'middleware', 'template', 'urls',
                                                         'utils', 'views', 'cache', 'core']:
                        # This looks like a Django core app test
                        new_test_files.append(tf)
                    else:
                        new_test_files.append(tf)
                
                if new_test_files != test_files:
                    logger.info(f"Retrying with converted test labels: {new_test_files}")
                    result = run_django_tests(container_name, repo_dir, new_test_files, timeout)
    
    return result

def run_django_tests(container_name: str, repo_dir: str, test_files: Optional[List[str]], timeout: int):
    """Run Django tests with specific test modules."""
    
    # Check if we have manage.py or need to use runtests.py
    check_manage = subprocess.run(
        ["docker", "exec", container_name, "test", "-f", f"{repo_dir}/manage.py"],
        capture_output=True
    )
    
    # For Django core development, ensure test dependencies are installed
    if check_manage.returncode != 0:
        ensure_django_test_dependencies(container_name, repo_dir)
    
    if check_manage.returncode == 0:
        # Use manage.py
        cmd = ["docker", "exec", "-w", repo_dir, container_name,
               "conda", "run", "-n", "testbed",
               "python", "manage.py", "test", "--verbosity=2", "--no-input"]
    else:
        # Use tests/runtests.py (Django core development)
        cmd = ["docker", "exec", "-w", f"{repo_dir}/tests", container_name,
               "conda", "run", "-n", "testbed",
               "python", "runtests.py", "--verbosity=2", "--no-input"]
    
    if test_files:
        # Add specific test modules
        cmd.extend(test_files)
        logger.info(f"Running Django tests: {test_files}")
    else:
        logger.info("Running all Django tests")
    
    return subprocess.run(
        cmd,
        capture_output=True, 
        text=True, 
        timeout=timeout
    )


def _parse_pytest(output: str) -> dict:
    """Extract pytest test counts from output."""
    
    lines = output.strip().split('\n')
    stats = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    
    # First, check if collection failed
    for line in lines:
        # Collection phase errors (file not found, import errors, etc)
        if "ERROR collecting" in line or "collection failed" in line.lower():
            stats["errors"] = 1
            return stats
            
        # pytest execution errors (usually config issues)
        if line.strip().startswith("ERROR:") or "INTERNALERROR>" in line:
            stats["errors"] = 1
            return stats
    
    # Look for pytest result summary
    for i, line in enumerate(lines):
        # Modern pytest summary line with timing info (most reliable)
        match = re.search(r'=+\s*([\d.]+s.*?)=+$', line)
        if match:
            summary_text = match.group(1)
            
            # Parse passed/failed from summary
            if re.search(r'(\d+)\s+passed', summary_text):
                stats["passed"] = int(re.search(r'(\d+)\s+passed', summary_text).group(1))
            if re.search(r'(\d+)\s+failed', summary_text):
                stats["failed"] = int(re.search(r'(\d+)\s+failed', summary_text).group(1))
            if re.search(r'(\d+)\s+error', summary_text):
                stats["errors"] = int(re.search(r'(\d+)\s+error', summary_text).group(1))
            if re.search(r'(\d+)\s+skipped', summary_text):
                stats["skipped"] = int(re.search(r'(\d+)\s+skipped', summary_text).group(1))
                
            # If we found counts, we're done
            if any(stats[k] > 0 for k in ["passed", "failed", "errors", "skipped"]):
                stats["collected"] = sum(stats.values())
                return stats
        
        # Alternative format without counts
        if "= no tests ran in" in line:
            # All tests were skipped/deselected
            stats["collected"] = 0
            return stats
            
        # Another format: "== 1 passed in 0.50s =="
        if re.match(r'^=+\s*\d+\s+(passed|failed|error|skipped)', line):
            parts = line.split()
            for i, part in enumerate(parts):
                if part in ['passed', 'failed', 'error', 'errors', 'skipped']:
                    try:
                        count = int(parts[i-1])
                        if part == 'error' or part == 'errors':
                            stats['errors'] = count
                        else:
                            stats[part.rstrip('s')] = count
                    except (ValueError, IndexError):
                        pass
    
    # Alternative: Look for collection count
    for line in lines:
        if "collected" in line and "item" in line:
            match = re.search(r'collected\s+(\d+)', line)
            if match:
                stats["collected"] = int(match.group(1))
                break
    
    # If nothing found but no error indicators, check if tests ran successfully
    if all(stats[k] == 0 for k in stats) and output.strip():
        # Look for test execution indicators
        if re.search(r'\.+\s*\[\s*\d+%\]', output) or re.search(r'PASSED|FAILED|SKIPPED', output):
            # Tests ran but we couldn't parse results - check for success indicators
            if "failed" not in output.lower() and "error" not in output.lower():
                # Seems like tests passed but format wasn't recognized
                test_count = len(re.findall(r'(?:PASSED|test_\w+.*?(?:PASSED|OK))', output))
                if test_count > 0:
                    stats["passed"] = test_count
                    stats["collected"] = test_count
            else:
                # There were failures/errors
                stats["errors"] = 1
    
    # Final validation
    if stats["collected"] == 0 and any(stats[k] > 0 for k in ["passed", "failed", "errors", "skipped"]):
        stats["collected"] = sum(stats.values())
    
    return stats


def _parse_django_output(output: str) -> dict:
    """Extract Django test counts from output."""
    
    stats = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    
    # Django test output patterns
    # "Ran 88 tests in 5.623s" followed by OK or FAILED
    ran_match = re.search(r'Ran (\d+) tests? in', output)
    if ran_match:
        stats["collected"] = int(ran_match.group(1))
        
        # Check if OK or FAILED
        if re.search(r'\nOK\s*$', output, re.MULTILINE):
            stats["passed"] = stats["collected"]
        elif re.search(r'\nFAILED\s*\(', output):
            # Parse failure details: "FAILED (failures=2, errors=1)"
            fail_match = re.search(r'FAILED\s*\(([^)]+)\)', output)
            if fail_match:
                details = fail_match.group(1)
                
                # Parse individual counts
                failures_match = re.search(r'failures?=(\d+)', details)
                if failures_match:
                    stats["failed"] = int(failures_match.group(1))
                
                errors_match = re.search(r'errors?=(\d+)', details)
                if errors_match:
                    stats["errors"] = int(errors_match.group(1))
                
                skipped_match = re.search(r'skipped?=(\d+)', details)
                if skipped_match:
                    stats["skipped"] = int(skipped_match.group(1))
                
                # Calculate passed as total minus failed/errors/skipped
                stats["passed"] = max(0, stats["collected"] - stats["failed"] - stats["errors"] - stats["skipped"])
            else:
                # Generic failure without details
                stats["failed"] = 1
                stats["passed"] = max(0, stats["collected"] - 1)
    else:
        # Fallback: count individual test results
        passed = len(re.findall(r'(\w+)\s+\(\S+\)\s+\.\.\.\s+ok', output))
        failed = len(re.findall(r'(\w+)\s+\(\S+\)\s+\.\.\.\s+FAIL', output))
        errors = len(re.findall(r'(\w+)\s+\(\S+\)\s+\.\.\.\s+ERROR', output))
        skipped = len(re.findall(r'(\w+)\s+\(\S+\)\s+\.\.\.\s+skipped', output))
        
        if passed + failed + errors + skipped > 0:
            stats["passed"] = passed
            stats["failed"] = failed
            stats["errors"] = errors
            stats["skipped"] = skipped
            stats["collected"] = passed + failed + errors + skipped
    
    return stats


@app.get("/health")
def health():
    return {"status": "ok", "service": "swe-tester-v2-fixed"}