"""
FastAPI micro-service v2: POST /test {instance_id, patch, timeout, test_files}
Runs specific tests inside the relevant Epoch SWE-Bench image and returns JSON stats.
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
    # Check if pytest exists
    check_cmd = ["docker", "exec", container_name, 
                 "conda", "run", "-n", "testbed", "which", "pytest"]
    check_result = subprocess.run(check_cmd, capture_output=True)
    
    if check_result.returncode != 0:
        # pytest not found, install it
        logger.info("pytest not found in testbed env, installing...")
        install_cmd = ["docker", "exec", container_name,
                       "conda", "run", "-n", "testbed", "pip", "install", "pytest"]
        install_result = subprocess.run(install_cmd, capture_output=True, text=True)
        if install_result.returncode != 0:
            logger.error(f"Failed to install pytest: {install_result.stderr}")
            return False
        logger.info("pytest installed successfully")
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
    
    # Base command
    cmd = ["docker", "exec", "-w", repo_dir, container_name, 
           "conda", "run", "-n", "testbed", "pytest"]
    
    if test_files:
        # Run only specific test files
        # Don't use -x flag to run all specified tests
        cmd.extend(["-v", "--tb=short", "--no-header", "-rN"])
        cmd.extend(test_files)
        logger.info(f"Running specific tests: {test_files}")
    else:
        # Fallback to running all tests (existing behavior)
        cmd.extend(["-xvs"])
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
        cmd = ["docker", "exec", "-w", f"{repo_dir}/tests", 
               "-e", f"PYTHONPATH={repo_dir}",
               container_name,
               "conda", "run", "-n", "testbed",
               "python", "runtests.py", "--verbosity=2"]
    
    if test_files:
        # Convert file paths to Django test labels
        test_labels = convert_to_django_test_labels(test_files)
        cmd.extend(test_labels)
        logger.info(f"Running Django tests: {test_labels}")
    else:
        # Run all tests
        logger.info("Running all Django tests")
    
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )


def convert_to_django_test_labels(test_files: List[str]) -> List[str]:
    """Convert file paths to Django test labels.
    
    Examples:
    - tests/validators/test_ipv4.py -> tests.validators.test_ipv4
    - tests/validators/ -> validators (strips 'tests/' prefix)
    - django/core/validators/tests.py -> django.core.validators.tests
    """
    test_labels = []
    
    for file_path in test_files:
        # Remove .py extension if present
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        
        # Remove trailing slashes
        file_path = file_path.rstrip('/')
        
        # Special handling for paths starting with 'tests/'
        # Django's test runner expects app names, not 'tests.app_name'
        if file_path.startswith('tests/') and '/' not in file_path[6:]:
            # e.g., "tests/validators" -> "validators"
            test_label = file_path[6:]  # Strip 'tests/' prefix
        else:
            # Convert slashes to dots for other paths
            test_label = file_path.replace('/', '.')
        
        # Remove trailing dots
        test_label = test_label.rstrip('.')
        
        test_labels.append(test_label)
    
    return test_labels


def _parse_pytest(text: str) -> dict:
    """Parse pytest output for test statistics."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    m = re.search(r"=+\s+(.*?)\s+=+", text)
    if m:
        summary = m.group(1)
        for key in stats:
            mm = re.search(fr"(\d+)\s+{key}", summary)
            if mm:
                stats[key] = int(mm.group(1))
    
    # Also check for "collected X items" to ensure tests ran
    collected = re.search(r"collected\s+(\d+)\s+item", text)
    if collected:
        stats["collected"] = int(collected.group(1))
    
    return stats


def _parse_django_output(text: str) -> dict:
    """Parse Django test output for statistics."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    # Django shows: "Ran X tests" and "FAILED (failures=Y, errors=Z)"
    ran_match = re.search(r"Ran (\d+) tests?", text)
    if ran_match:
        total = int(ran_match.group(1))
        
        # Check for failures/errors
        failed_match = re.search(r"FAILED.*failures=(\d+)", text)
        errors_match = re.search(r"FAILED.*errors=(\d+)", text)
        
        if failed_match:
            stats["failed"] = int(failed_match.group(1))
        if errors_match:
            stats["errors"] = int(errors_match.group(1))
        
        # If we see "OK" in output, all tests passed
        if "OK" in text and "FAILED" not in text:
            stats["passed"] = total
        else:
            stats["passed"] = total - stats["failed"] - stats["errors"]
    
    return stats


# Health check endpoint
@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.0"}