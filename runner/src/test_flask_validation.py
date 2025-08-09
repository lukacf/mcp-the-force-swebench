#!/usr/bin/env python3
"""Test the evaluator with a Flask instance."""

import json
import logging
import tempfile
from pathlib import Path

from evaluator import evaluate_patch
from git_utils import ensure_bare_mirror, checkout_worktree

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Load the Flask instance
    instance_json = """{"instance_id": "pallets__flask-5014", "problem_statement": "Require a non-empty name for Blueprints\\nThings do not work correctly if a Blueprint is given an empty name (e.g. #4944).\\r\\nIt would be helpful if a `ValueError` was raised when trying to do that.\\n", "repo": "pallets/flask", "base_commit": "7ee9ceb71e868944a46e1ff00b506772a53a4f1d", "patch": "diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py\\n--- a/src/flask/blueprints.py\\n+++ b/src/flask/blueprints.py\\n@@ -190,6 +190,9 @@ def __init__(\\n             root_path=root_path,\\n         )\\n \\n+        if not name:\\n+            raise ValueError(\\"'name' may not be empty.\\")\\n+\\n         if \\".\\\" in name:\\n             raise ValueError(\\"'name' may not contain a dot '.' character.\\")\\n \\n", "test_patch": "diff --git a/tests/test_blueprints.py b/tests/test_blueprints.py\\n--- a/tests/test_blueprints.py\\n+++ b/tests/test_blueprints.py\\n@@ -256,6 +256,11 @@ def test_dotted_name_not_allowed(app, client):\\n         flask.Blueprint(\\"app.ui\\", __name__)\\n \\n \\n+def test_empty_name_not_allowed(app, client):\\n+    with pytest.raises(ValueError):\\n+        flask.Blueprint(\\"\\", __name__)\\n+\\n+\\n def test_dotted_names_from_app(app, client):\\n     test = flask.Blueprint(\\"test\\", __name__)\\n \\n"}"""
    
    instance = json.loads(instance_json)
    
    # Setup cache directory
    cache_dir = Path("../artifacts/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure we have a mirror
    repo_url = f"https://github.com/{instance['repo']}"
    logger.info(f"Ensuring mirror for {repo_url}")
    ensure_bare_mirror(repo_url, cache_dir)
    
    # Use checkout_worktree context manager
    with checkout_worktree(repo_url, instance['base_commit'], cache_dir) as workdir:
        logger.info(f"Using worktree at {workdir}")
        
        # Install dependencies
        logger.info("Installing Flask dependencies...")
        import subprocess
        
        # Create a virtual environment
        venv_dir = workdir / ".venv"
        subprocess.run(["python", "-m", "venv", str(venv_dir)], cwd=workdir, check=True)
        
        # Install Flask in development mode
        pip_path = venv_dir / "bin" / "pip"
        subprocess.run([str(pip_path), "install", "-e", ".", "-q"], cwd=workdir, check=True)
        subprocess.run([str(pip_path), "install", "pytest", "-q"], cwd=workdir, check=True)
        
        # Test 1: Good patch should pass
        logger.info("=" * 60)
        logger.info("TEST 1: Good patch (should PASS)")
        logger.info("=" * 60)
        
        result = evaluate_patch(instance, instance['patch'], str(workdir), force_local=True)
        
        if result['passed']:
            logger.info("✅ GOOD PATCH PASSED - Correct!")
        else:
            logger.error(f"❌ GOOD PATCH FAILED - Incorrect! Error: {result['error']}")
            logger.error(f"Test output:\n{result['test_output']}")
        
        # Reset to clean state
        subprocess.run(["git", "checkout", "."], cwd=workdir, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=workdir, check=True)
        
        # Test 2: Empty patch should fail
        logger.info("=" * 60)
        logger.info("TEST 2: Empty patch (should FAIL)")
        logger.info("=" * 60)
        
        result = evaluate_patch(instance, "", str(workdir), force_local=True)
        
        if not result['passed']:
            logger.info("✅ EMPTY PATCH FAILED - Correct!")
        else:
            logger.error("❌ EMPTY PATCH PASSED - Incorrect!")
            logger.error(f"Test output:\n{result['test_output']}")
        
        # Reset to clean state
        subprocess.run(["git", "checkout", "."], cwd=workdir, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=workdir, check=True)
        
        # Test 3: Bad patch (introduce a syntax error)
        logger.info("=" * 60)
        logger.info("TEST 3: Bad patch with syntax error (should FAIL)")
        logger.info("=" * 60)
        
        bad_patch = """diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py
--- a/src/flask/blueprints.py
+++ b/src/flask/blueprints.py
@@ -190,6 +190,9 @@ def __init__(
             root_path=root_path,
         )
 
+        if not name
+            raise ValueError("'name' may not be empty.")
+
         if "." in name:
             raise ValueError("'name' may not contain a dot '.' character.")
 """
        
        result = evaluate_patch(instance, bad_patch, str(workdir), force_local=True)
        
        if not result['passed']:
            logger.info("✅ BAD PATCH FAILED - Correct!")
        else:
            logger.error("❌ BAD PATCH PASSED - Incorrect!")
            logger.error(f"Test output:\n{result['test_output']}")
        
        logger.info("=" * 60)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 60)

if __name__ == "__main__":
    import sys
    try:
        main()
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)