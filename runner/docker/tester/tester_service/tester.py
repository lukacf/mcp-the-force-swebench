"""
FastAPI micro-service:  POST /test  {repo, base_commit, patch, timeout}
Runs tests inside the relevant Epoch SWE-Bench image and returns JSON stats.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import subprocess, tempfile, os, uuid, time, json, re, shutil, textwrap

SCRATCH = "/scratch/repos"          # bind-mount host SSD here
os.makedirs(SCRATCH, exist_ok=True)

app = FastAPI(title="swe-tester", version="0.1.0")


class Request(BaseModel):
    instance_id: str = Field(..., description="SWE-Bench instance ID, e.g. django__django-16595")
    patch:       str
    timeout:     int = 900


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

        # 4. run pytest (quieter output)
        # The Epoch AI images have pytest in the 'testbed' conda environment
        test = subprocess.run(
            ["docker", "exec", "-w", repo_dir, cname, "conda", "run", "-n", "testbed", "pytest", "-xvs"],
            capture_output=True, text=True, timeout=r.timeout
        )
        out = test.stdout + "\n" + test.stderr
        stats = _parse_pytest(out)
        tail = "\n".join(out.splitlines()[-30:])

        return {
            **stats,
            "duration": round(time.time() - t0, 2),
            "log_tail": tail
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "pytest timed-out")

    finally:
        subprocess.run(["docker", "rm", "-f", cname],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _parse_pytest(text: str) -> dict:
    """very small summariser"""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    m = re.search(r"=+\s+(.*?)\s+=+", text)
    if m:
        for key in stats:
            mm = re.search(fr"(\d+)\s+{key}", m.group(1))
            if mm:
                stats[key] = int(mm.group(1))
    return stats