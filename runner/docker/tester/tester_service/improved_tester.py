"""
Improved tester that handles both pytest and Django test runners.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import subprocess, tempfile, os, uuid, time, json, re

SCRATCH = "/scratch/repos"
os.makedirs(SCRATCH, exist_ok=True)

app = FastAPI(title="swe-tester-v2", version="0.2.0")


class Request(BaseModel):
    instance_id: str = Field(..., description="SWE-Bench instance ID")
    patch: str
    timeout: int = 900
    test_files: list[str] = Field(default_factory=list, description="Specific test files to run")


@app.post("/test")
def run_test(r: Request):
    t0 = time.time()

    # Epoch AI images use instance_id format
    image = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{r.instance_id}:latest"
    
    # lazy-pull (ignore failure – image may already exist locally)
    subprocess.run(["docker", "pull", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cname = f"swe-{uuid.uuid4().hex[:8]}"
    workdir = f"/workspace"
    host_repo_dir = os.path.join(SCRATCH, r.instance_id)
    os.makedirs(host_repo_dir, exist_ok=True)

    try:
        # 1. start container (detached)
        subprocess.run([
            "docker", "run", "-d", "--name", cname,
            "-v", f"{host_repo_dir}:{workdir}/scratch",
            "-w", workdir,
            image, "sleep", "infinity"
        ], check=True, stdout=subprocess.DEVNULL)

        # 2. Find the repo directory inside the container
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
                raise HTTPException(422, f"Patch failed:\\n{proc.stderr.decode()[:400]}")

        # 4. Detect test framework and run tests
        # Check if Django project
        manage_py_check = subprocess.run(
            ["docker", "exec", cname, "test", "-f", f"{repo_dir}/manage.py"],
            capture_output=True
        )
        
        if manage_py_check.returncode == 0:
            # Django project
            if r.test_files:
                # Convert file paths to Django test modules
                test_modules = []
                for tf in r.test_files:
                    if tf.endswith('.py'):
                        module = tf.replace('/', '.').replace('.py', '')
                    else:
                        module = tf.replace('/', '.')
                    test_modules.append(module)
                
                test_cmd = ["python", "manage.py", "test", "--verbosity=2"] + test_modules
            else:
                test_cmd = ["python", "manage.py", "test", "--verbosity=2"]
            
            test = subprocess.run(
                ["docker", "exec", "-w", repo_dir, cname] + test_cmd,
                capture_output=True, text=True, timeout=r.timeout
            )
            out = test.stdout + "\\n" + test.stderr
            stats = _parse_django_output(out)
        else:
            # Use pytest
            if r.test_files:
                test_cmd = ["pytest", "-xvs"] + r.test_files
            else:
                test_cmd = ["pytest", "-xvs"]
            
            test = subprocess.run(
                ["docker", "exec", "-w", repo_dir, cname, "conda", "run", "-n", "testbed"] + test_cmd,
                capture_output=True, text=True, timeout=r.timeout
            )
            out = test.stdout + "\\n" + test.stderr
            stats = _parse_pytest(out)
        
        tail = "\\n".join(out.splitlines()[-30:])

        return {
            **stats,
            "duration": round(time.time() - t0, 2),
            "log_tail": tail
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Test execution timed-out")

    finally:
        subprocess.run(["docker", "rm", "-f", cname],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _parse_pytest(text: str) -> dict:
    """Parse pytest output"""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    m = re.search(r"=+\\s+(.*)\\s+=+", text)
    if m:
        for key in stats:
            mm = re.search(fr"(\\d+)\\s+{key}", m.group(1))
            if mm:
                stats[key] = int(mm.group(1))
    return stats


def _parse_django_output(text: str) -> dict:
    """Parse Django test output"""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    # Django shows: "Ran X tests" and "FAILED (failures=Y, errors=Z)"
    ran_match = re.search(r"Ran (\\d+) tests?", text)
    if ran_match:
        total = int(ran_match.group(1))
        
        # Check for failures/errors
        failed_match = re.search(r"FAILED.*failures=(\\d+)", text)
        errors_match = re.search(r"FAILED.*errors=(\\d+)", text)
        
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