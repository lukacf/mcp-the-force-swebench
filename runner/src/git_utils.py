"""Git utilities for managing mirrors and worktrees."""

import subprocess
import logging
import shutil
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List
import tempfile
import fcntl

logger = logging.getLogger(__name__)


def get_repo_name_from_url(repo_url: str) -> str:
    """Extract repository name from GitHub URL."""
    # Handle formats like:
    # - https://github.com/django/django
    # - https://github.com/django/django.git
    # - django/django
    
    if '/' not in repo_url:
        return repo_url
        
    parts = repo_url.rstrip('.git').split('/')
    if len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    return parts[-1]


def ensure_bare_mirror(
    repo_url: str,
    cache_dir: Path,
    update: bool = False,
    refresh: bool = False
) -> Path:
    """Ensure we have a bare mirror of the repository."""
    
    repo_name = get_repo_name_from_url(repo_url)
    mirror_path = cache_dir / f"{repo_name}.git"
    
    # Use a lock file to prevent concurrent access
    lock_file = cache_dir / f"{repo_name}.lock"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    with open(lock_file, 'w') as lock:
        # Acquire exclusive lock
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        
        try:
            if mirror_path.exists():
                if update or refresh:
                    logger.info(f"Updating mirror: {mirror_path}")
                    subprocess.run(
                        ['git', 'fetch', '--all', '--tags', '--prune'],
                        cwd=mirror_path,
                        check=True,
                        capture_output=True
                    )
                else:
                    logger.info(f"Using existing mirror: {mirror_path}")
            else:
                # Check if we're in production mode (not precaching)
                if os.environ.get('SWEBENCH_REQUIRE_CACHE') == '1':
                    raise RuntimeError(
                        f"{mirror_path} missing – did you forget to run scripts/precache_repos.py?"
                    )
                
                logger.info(f"Creating new mirror: {mirror_path}")
                subprocess.run(
                    ['git', 'clone', '--mirror', repo_url, str(mirror_path)],
                    check=True,
                    capture_output=True
                )
            
            return mirror_path
            
        finally:
            # Lock is automatically released when file is closed
            pass


def _link_runtime_dirs(worktree_path: Path):
    """Create symlinks to runtime directories in the worktree."""
    # Find project root (go up from src/ to runner/ to project root)
    project_root = Path(__file__).resolve().parents[2]
    
    for name in ('.mcp-the-force', '.claude', '.gcp', 'claude_hooks'):
        src = project_root / name
        dst = worktree_path / name
        
        if dst.exists() or not src.exists():
            continue
            
        try:
            dst.symlink_to(src, target_is_directory=True)
            logger.debug(f"Linked {name} -> {src}")
        except Exception as e:
            logger.warning(f"Failed to link {name}: {e}")


@contextmanager
def checkout_worktree(
    repo_url: str,
    commit_hash: str,
    cache_dir: Path = None,
    work_dir: Path = None
):
    """Context manager for checking out a worktree at a specific commit."""
    
    if cache_dir is None:
        cache_dir = Path("runner/artifacts/cache")
    if work_dir is None:
        work_dir = Path("runner/artifacts/worktrees")
    
    # Ensure we have the mirror
    mirror_path = ensure_bare_mirror(repo_url, cache_dir)
    
    # Create a temporary directory for the worktree
    worktree_path = None
    
    try:
        # Create worktree directory
        work_dir.mkdir(parents=True, exist_ok=True)
        worktree_dir = tempfile.mkdtemp(dir=work_dir, prefix=f"wt_{commit_hash[:8]}_")
        worktree_path = Path(worktree_dir)
        
        logger.info(f"Creating worktree at {worktree_path} for commit {commit_hash}")
        
        # Add worktree at specific commit
        subprocess.run(
            ['git', 'worktree', 'add', '--detach', str(worktree_path), commit_hash],
            cwd=mirror_path,
            check=True,
            capture_output=True
        )
        
        # Link runtime directories
        _link_runtime_dirs(worktree_path)
        
        # Yield the worktree path for use
        yield worktree_path
        
    finally:
        # Clean up worktree
        if worktree_path and worktree_path.exists():
            logger.info(f"Cleaning up worktree: {worktree_path}")
            
            # Remove worktree from git
            try:
                subprocess.run(
                    ['git', 'worktree', 'remove', '--force', str(worktree_path)],
                    cwd=mirror_path,
                    capture_output=True
                )
            except:
                # If git worktree remove fails, try manual cleanup
                pass
            
            # Ensure directory is removed
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)


def get_changed_files(workdir: Path) -> List[str]:
    """Get list of changed files in the working directory."""
    
    result = subprocess.run(
        ['git', 'diff', '--name-only'],
        cwd=workdir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        return [f.strip() for f in result.stdout.split('\n') if f.strip()]
    return []


def create_commit(workdir: Path, message: str) -> Optional[str]:
    """Create a commit with all changes and return the commit hash."""
    
    try:
        # Add all changes
        subprocess.run(
            ['git', 'add', '-A'],
            cwd=workdir,
            check=True,
            capture_output=True
        )
        
        # Create commit
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=workdir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Get the commit hash
            hash_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=workdir,
                capture_output=True,
                text=True
            )
            return hash_result.stdout.strip()
        
    except Exception as e:
        logger.error(f"Failed to create commit: {e}")
    
    return None


def generate_diff(workdir: Path, base_commit: str = 'HEAD~1') -> str:
    """Generate a diff from the current state against a base commit."""
    
    result = subprocess.run(
        ['git', 'diff', base_commit],
        cwd=workdir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        return result.stdout
    return ""