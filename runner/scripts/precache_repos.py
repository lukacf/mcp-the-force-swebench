#!/usr/bin/env python3
"""
Pre-download all repos & commits referenced in swe_bench_instances.jsonl
Run once before firing the worker fleet.
"""

import json
import subprocess
import concurrent.futures
import os
import sys
from pathlib import Path

# Add parent directory to path to import runner modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_data import load_instances
from src.git_utils import ensure_bare_mirror, get_repo_name_from_url

CACHE_ROOT = Path("runner/artifacts/cache")
MAX_PARALLEL = 8  # saturate your network pipe


def warm_repo(repo: str, commits: set[str]):
    """Clone mirror + fetch required commits."""
    url = f"https://github.com/{repo}"
    mirror = ensure_bare_mirror(url, CACHE_ROOT, update=False)

    # Pull each commit (depth-1) so worktree add never hits the network
    for h in commits:
        try:
            subprocess.run(
                ["git", "--git-dir", str(mirror), "fetch", "origin", h, "--depth=1",
                 "--filter=blob:none"],  # <-- keep it light
                check=True, capture_output=True
            )
            print(f"  ✓ {repo}@{h[:7]}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {repo}@{h[:7]} - {e.stderr.decode().strip()}")


def main():
    instances = load_instances()  # already cached JSONL
    commits_by_repo: dict[str, set[str]] = {}

    for inst in instances:
        repo = inst["repo"]  # e.g. "django/django"
        commits_by_repo.setdefault(repo, set()).add(inst["base_commit"])

    print(f"{len(commits_by_repo)} unique repos, "
          f"{sum(len(s) for s in commits_by_repo.values())} commits to fetch")

    # Parallelise mirror fetches; inside each, the per-commit fetch is serial.
    with concurrent.futures.ThreadPoolExecutor(MAX_PARALLEL) as exe:
        futures = [
            exe.submit(warm_repo, repo, commits)
            for repo, commits in commits_by_repo.items()
        ]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # will raise if clone/fetch failed

    print("✅ precache complete")


if __name__ == "__main__":
    main()