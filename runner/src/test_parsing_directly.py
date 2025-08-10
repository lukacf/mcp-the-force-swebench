#!/usr/bin/env python3
"""Test the parsing function directly."""

import re

log_tail = """sympy/interactive/session.py:316
  /testbed/sympy/interactive/session.py:316: DeprecationWarning: invalid escape sequence \/
    \"\"\"

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
                                DO *NOT* COMMIT!                                
======================== 1 failed, 96 warnings in 0.15s ========================


ERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)"""

def _parse_pytest(text: str) -> dict:
    """Parse pytest output for test statistics."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    print(f"Parsing text of length {len(text)}")
    
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    m = re.search(r"=+\s+(.*?)\s+=+", text)
    if m:
        print(f"Found summary match: '{m.group(1)}'")
        summary = m.group(1)
        for key in stats:
            mm = re.search(fr"(\d+)\s+{key}", summary)
            if mm:
                print(f"  Found {key}: {mm.group(1)}")
                stats[key] = int(mm.group(1))
    else:
        print("No summary match found")
    
    # Also check for "collected X items" to ensure tests ran
    collected = re.search(r"collected\s+(\d+)\s+item", text)
    if collected:
        stats["collected"] = int(collected.group(1))
        print(f"Found collected: {collected.group(1)}")
        
        # If we collected tests but parsed stats show 0 for everything,
        # and we see "X passed in" pattern, it means all tests passed
        if stats["passed"] == 0 and stats["failed"] == 0 and stats["errors"] == 0:
            print("All stats are 0, checking for all passed pattern...")
            all_passed = re.search(r"(\d+)\s+passed\s+in\s+[\d.]+s", text)
            if all_passed:
                print(f"Found all passed: {all_passed.group(1)}")
                stats["passed"] = int(all_passed.group(1))
    
    return stats

# Test the function
result = _parse_pytest(log_tail)
print(f"\nFinal result: {result}")

# Let's try different regex patterns
print("\n\nTrying alternative patterns:")

# More flexible pattern
m2 = re.search(r"=+\s*(.+?)\s*=+", log_tail, re.DOTALL)
if m2:
    print(f"Alternative match: '{m2.group(1)}'")
    
# Direct search for failure count
failed = re.search(r"(\d+)\s+failed", log_tail)
if failed:
    print(f"Direct failed search: {failed.group(1)}")