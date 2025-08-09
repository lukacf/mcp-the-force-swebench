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
            test_result = run_django_tests(cname, repo_dir, r.test_files, r.timeout)
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


def run_django_tests(container_name: str, repo_dir: str, test_files: Optional[List[str]], timeout: int):
    """Run Django tests with specific test modules."""
    
    # Check if we have manage.py or need to use runtests.py
    check_manage = subprocess.run(
        ["docker", "exec", container_name, "test", "-f", f"{repo_dir}/manage.py"],
        capture_output=True
    )
    
    if check_manage.returncode == 0:
        # Use manage.py
        cmd = ["docker", "exec", "-w", repo_dir, container_name,
               "python", "manage.py", "test", "--verbosity=2", "--no-input"]
    else:
        # Use tests/runtests.py (Django core development)
        cmd = ["docker", "exec", "-w", f"{repo_dir}/tests", 
               "-e", f"PYTHONPATH={repo_dir}",
               container_name,
               "python", "runtests.py", "--verbosity=2", "--no-capture"]
    
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
    - tests/validators/ -> tests.validators
    - django/core/validators/tests.py -> django.core.validators.tests
    """
    test_labels = []
    
    for file_path in test_files:
        # Remove .py extension if present
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        
        # Convert slashes to dots
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