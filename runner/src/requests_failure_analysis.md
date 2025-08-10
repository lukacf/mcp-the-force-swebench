# PSF/Requests Validation Failure Analysis

## Problem Summary
All 8 psf/requests instances failed validation (0% pass rate) due to Python compatibility issues.

## Root Cause
The requests library in the Docker images has outdated imports that are incompatible with Python 3.3+:

```python
# In /testbed/requests/packages/urllib3/_collections.py:7
from collections import MutableMapping  # This should be: from collections.abc import MutableMapping
```

## Specific Errors

1. **Import Error** (Python 3.11):
   ```
   ImportError: cannot import name 'MutableMapping' from 'collections'
   ```

2. **TypeError** in urllib3:
   ```
   TypeError: __init__() got an unexpected keyword argument 'strict'
   ```
   This happens because HTTPConnection no longer accepts 'strict' parameter in newer Python versions.

3. **DeprecationWarnings**:
   - Invalid escape sequences in docstrings
   - Using `is` with literals

## Test Results
- psf__requests-1142: 5 passed, 21 failed
- psf__requests-2931: 85 passed, 81 errors
- psf__requests-6028: 193 passed, 8 errors
- psf__requests-5414: 129 passed, 158 errors
- psf__requests-1724: 85 passed, 2 failed
- psf__requests-1766: 88 passed, 2 failed
- psf__requests-1921: 117 passed, 1 failed
- psf__requests-2317: Timeout (no tests ran)

## Current Test Execution Method

From `tester.py`:
```python
def run_pytest_tests(container_name: str, repo_dir: str, test_files: Optional[List[str]], timeout: int):
    """Run pytest with specific test files or all tests."""
    
    # Ensure pytest is installed
    ensure_pytest_installed(container_name)
    
    # Base command
    cmd = ["docker", "exec", "-w", repo_dir, container_name, 
           "conda", "run", "-n", "testbed", "pytest"]
    
    if test_files:
        cmd.extend(["-v", "--tb=short", "--no-header", "-rN"])
        cmd.extend(test_files)
```

## Key Issue
The Docker images for psf/requests contain very old versions of the requests library (likely from 2012-2013 based on the import patterns) that are incompatible with Python 3.11 runtime.
