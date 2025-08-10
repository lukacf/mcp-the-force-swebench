#!/usr/bin/env python3
"""Test pytest output parsing."""

import re

# Sample output from the log
sample_output = """
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
                                DO *NOT* COMMIT!                                
======================== 1 failed, 96 warnings in 0.15s ========================


ERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)
"""

# Current regex
m = re.search(r"=+\s+(.*?)\s+=+", sample_output)
if m:
    print(f"Found summary: '{m.group(1)}'")
    summary = m.group(1)
    
    # Try to extract failed count
    failed_match = re.search(r"(\d+)\s+failed", summary)
    if failed_match:
        print(f"Failed: {failed_match.group(1)}")
else:
    print("No match found with current regex")

# Alternative regex that might work better
m2 = re.search(r"=+\s*(.+?)\s*=+", sample_output, re.MULTILINE)
if m2:
    print(f"\nAlternative regex found: '{m2.group(1)}'")
    summary2 = m2.group(1)
    
    failed_match2 = re.search(r"(\d+)\s+failed", summary2)
    if failed_match2:
        print(f"Failed: {failed_match2.group(1)}")

# Let's also test the "all passed" case
sample_passed = "==================== 7 passed, 96 warnings in 0.51s ===================="
m3 = re.search(r"=+\s*(.+?)\s*=+", sample_passed)
if m3:
    print(f"\nPassed case: '{m3.group(1)}'")
    summary3 = m3.group(1)
    passed_match = re.search(r"(\d+)\s+passed", summary3)
    if passed_match:
        print(f"Passed: {passed_match.group(1)}")