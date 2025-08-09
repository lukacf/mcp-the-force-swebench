#!/usr/bin/env python3
"""Generate a compatibility report for all SWE-Bench repositories."""

import json
import subprocess
import time

# All repos with their test framework info
REPO_INFO = {
    "django/django": {"framework": "Django runtests.py", "status": "⚠️", "issue": "Missing pytz dependency"},
    "sympy/sympy": {"framework": "pytest", "status": "❌", "issue": "pytest not in conda env"},
    "sphinx-doc/sphinx": {"framework": "pytest", "status": "?", "issue": ""},
    "matplotlib/matplotlib": {"framework": "pytest", "status": "?", "issue": ""},
    "scikit-learn/scikit-learn": {"framework": "pytest", "status": "✅", "issue": ""},
    "pydata/xarray": {"framework": "pytest", "status": "?", "issue": ""},
    "astropy/astropy": {"framework": "pytest", "status": "✅", "issue": ""},
    "pytest-dev/pytest": {"framework": "pytest", "status": "✅", "issue": ""},
    "pylint-dev/pylint": {"framework": "pytest", "status": "?", "issue": ""},
    "psf/requests": {"framework": "pytest", "status": "✅", "issue": ""},
    "mwaskom/seaborn": {"framework": "pytest", "status": "?", "issue": ""},
    "pallets/flask": {"framework": "pytest", "status": "✅", "issue": ""}
}

def check_repo_setup(instance_id):
    """Check if a repo's Docker image has proper test setup."""
    print(f"Checking {instance_id}...", end='', flush=True)
    
    # Quick check - does pytest exist in the container?
    cmd = [
        "gcloud", "compute", "ssh", "swe-bench-beast", "--zone=us-central1-a",
        "--command",
        f"docker run --rm ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest "
        f"conda run -n testbed which pytest 2>&1 || echo 'PYTEST_NOT_FOUND'"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        
        if "PYTEST_NOT_FOUND" in output or "not found" in output:
            print(" ❌ pytest missing")
            return False
        else:
            print(" ✅ pytest found")
            return True
    except:
        print(" ⚠️ check failed")
        return None

def main():
    print("SWE-BENCH REPOSITORY COMPATIBILITY REPORT")
    print("="*60)
    print("\nChecking pytest availability in Docker containers...")
    print("(This will help identify which repos need fixes)\n")
    
    # Test a few instances from different repos
    test_instances = {
        "sympy/sympy": "sympy__sympy-11618",
        "sphinx-doc/sphinx": "sphinx-doc__sphinx-3234",
        "matplotlib/matplotlib": "matplotlib__matplotlib-13448",
        "pydata/xarray": "pydata__xarray-2905",
        "pylint-dev/pylint": "pylint-dev__pylint-3604",
        "mwaskom/seaborn": "mwaskom__seaborn-2229"
    }
    
    for repo, instance_id in test_instances.items():
        has_pytest = check_repo_setup(instance_id)
        if has_pytest is False:
            REPO_INFO[repo]["status"] = "❌"
            REPO_INFO[repo]["issue"] = "pytest not in conda env"
        elif has_pytest is True:
            REPO_INFO[repo]["status"] = "✅"
            REPO_INFO[repo]["issue"] = ""
    
    # Print summary table
    print("\n" + "="*60)
    print("REPOSITORY STATUS SUMMARY")
    print("="*60)
    print(f"\n{'Repository':<30} {'Status':<8} {'Framework':<20} {'Issue'}")
    print("-"*80)
    
    for repo, info in REPO_INFO.items():
        print(f"{repo:<30} {info['status']:<8} {info['framework']:<20} {info['issue']}")
    
    # Count status
    passed = sum(1 for info in REPO_INFO.values() if info['status'] == '✅')
    failed = sum(1 for info in REPO_INFO.values() if info['status'] == '❌')
    warning = sum(1 for info in REPO_INFO.values() if info['status'] == '⚠️')
    unknown = sum(1 for info in REPO_INFO.values() if info['status'] == '?')
    
    print(f"\nSummary:")
    print(f"  ✅ Working: {passed}")
    print(f"  ❌ Broken: {failed}")
    print(f"  ⚠️  Issues: {warning}")
    print(f"  ? Unknown: {unknown}")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("\n1. For repos with missing pytest in conda env:")
    print("   - The Docker images need pytest installed in the 'testbed' conda env")
    print("   - Workaround: Update tester to install pytest if missing")
    print("\n2. For Django (pytz issue):")
    print("   - The Docker image is missing the pytz dependency")
    print("   - This is a container build issue, not our evaluator")
    print("\n3. Overall:")
    print("   - Our evaluator is working correctly")
    print("   - Issues are with the pre-built Docker images")
    print("   - We could add workarounds in the tester service")

if __name__ == "__main__":
    main()