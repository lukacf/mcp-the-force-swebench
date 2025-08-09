# Django Dependencies Solution for SWE-Bench

## Problem
Django instances fail with `ModuleNotFoundError: No module named 'pytz'` when running Django's test suite using `tests/runtests.py` in pre-built Docker containers.

## Solution Implemented

### 1. Automatic Django Test Dependencies Installation
The `ensure_django_test_dependencies()` function now:
- Checks for test requirements files in common locations:
  - `/tests/requirements/py3.txt` (Django's standard location)
  - `/tests/requirements/tests.txt`
  - `/tests/requirements.txt`
  - `/test-requirements.txt`
  - `/requirements-test.txt`
- If found, installs dependencies from the requirements file
- If not found, installs common Django test dependencies: pytz, jinja2, numpy, Pillow, PyYAML, sqlparse
- Handles version-specific dependencies for Django 3.2+

### 2. Conda Environment Integration
- All Django tests now run within the conda `testbed` environment
- Both `manage.py` and `runtests.py` commands use `conda run -n testbed`
- This ensures consistent Python environment usage

### 3. Automatic Retry on Import Errors
The `run_django_tests_with_retry()` function:
- Runs tests and checks for ModuleNotFoundError
- If found, attempts to install the missing module
- Retries the tests after successful installation
- Handles module name to package name mappings (e.g., PIL → Pillow)

## How It Works

1. When Django tests are requested:
   - System detects Django core (no manage.py) vs Django project (has manage.py)
   - For Django core, calls `ensure_django_test_dependencies()`

2. Dependency installation process:
   - First tries to find and install from requirements files
   - Falls back to installing common dependencies
   - Checks Django version for version-specific requirements

3. Test execution:
   - Runs tests in conda environment
   - If import error occurs, installs missing module and retries

## Benefits

- **Robustness**: Works across different Django versions in SWE-Bench
- **Efficiency**: Only installs what's needed, checks requirements files first
- **Reliability**: Automatic retry handles edge cases
- **Compatibility**: Maintains existing behavior for non-Django projects

## Additional Recommendations

1. **Monitor Success Rate**: Track which Django instances still fail after this fix
2. **Cache Dependencies**: Consider caching installed dependencies for faster subsequent runs
3. **Expand Module Mappings**: Add more module-to-package mappings as needed
4. **Version-Specific Handling**: Add more Django version-specific dependency handling as issues arise

## Testing

To test the solution:
1. Run a Django instance that previously failed with pytz error
2. Verify that dependencies are installed automatically
3. Check that tests run successfully after dependency installation
4. Test with different Django versions to ensure compatibility