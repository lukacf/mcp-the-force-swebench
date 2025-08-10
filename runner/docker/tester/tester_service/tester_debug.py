"""
Debug version of tester with logging to understand parsing issues.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import subprocess, tempfile, os, uuid, time, json, re, shutil, textwrap
import logging

SCRATCH = "/scratch/repos"
os.makedirs(SCRATCH, exist_ok=True)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="swe-tester-debug", version="2.0.1")


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

        # 4. Run tests (simplified for SymPy)
        repo_name = r.instance_id.split("__")[0]
        
        # Ensure pytest is installed
        subprocess.run(
            ["docker", "exec", cname, "conda", "run", "-n", "testbed", "pip", "install", "pytest"],
            capture_output=True
        )
        
        # Run tests
        cmd = ["docker", "exec", "-w", repo_dir, cname, 
               "conda", "run", "-n", "testbed", "pytest"]
        
        if r.test_files:
            cmd.extend(["-v", "--tb=short", "--no-header", "-rN"])
            cmd.extend(r.test_files)
        else:
            cmd.extend(["-xvs"])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        test_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=r.timeout
        )
        
        out = test_result.stdout + "\\n" + test_result.stderr
        
        # DEBUG: Log the output
        logger.debug(f"Exit code: {test_result.returncode}")
        logger.debug(f"Output length: {len(out)}")
        logger.debug(f"Last 500 chars:\\n{out[-500:]}")
        
        # Parse results
        stats = _parse_pytest_debug(out)
        
        tail = "\\n".join(out.splitlines()[-50:])

        return {
            **stats,
            "duration": round(time.time() - t0, 2),
            "log_tail": tail,
            "test_files_run": r.test_files or ["all"],
            "exit_code": test_result.returncode
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Test execution timed-out")

    finally:
        subprocess.run(["docker", "rm", "-f", cname],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _parse_pytest_debug(text: str) -> dict:
    """Parse pytest output with debug logging."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    logger.debug("Parsing pytest output...")
    
    # Look for summary line
    m = re.search(r"=+\\s+(.*?)\\s+=+", text)
    if m:
        summary = m.group(1)
        logger.debug(f"Found summary: '{summary}'")
        
        for key in stats:
            mm = re.search(fr"(\\d+)\\s+{key}", summary)
            if mm:
                logger.debug(f"  {key}: {mm.group(1)}")
                stats[key] = int(mm.group(1))
    else:
        logger.debug("No summary line found")
    
    # Check for collected
    collected = re.search(r"collected\\s+(\\d+)\\s+item", text)
    if collected:
        stats["collected"] = int(collected.group(1))
        logger.debug(f"Collected: {collected.group(1)}")
    
    logger.debug(f"Final stats: {stats}")
    
    return stats


@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.1-debug"}