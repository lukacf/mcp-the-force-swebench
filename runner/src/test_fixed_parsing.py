#!/usr/bin/env python3
"""Test the fixed parsing function."""

import re

# Sample outputs to test
test_cases = [
    # Case 1: Failed test
    ("""============================= test session starts ==============================
platform linux -- Python 3.9.20, pytest-8.4.1, pluggy-1.6.0
collected 1 item

sympy/geometry/tests/test_point.py::test_issue_11617 FAILED              [100%]

=================================== FAILURES ===================================
_______________________________ test_issue_11617 _______________________________
AssertionError
======================== 1 failed, 96 warnings in 0.15s ========================""",
     {"passed": 0, "failed": 1, "errors": 0, "collected": 1}),
    
    # Case 2: Passed test
    ("""============================= test session starts ==============================
collected 5 items

test_sample.py .....                                                        [100%]

============================== 5 passed in 0.42s ===============================""",
     {"passed": 5, "failed": 0, "errors": 0, "collected": 5}),
    
    # Case 3: Mixed results
    ("""============================= test session starts ==============================
collected 10 items

test_mixed.py ..F..E....                                                   [100%]

=================== 2 failed, 7 passed, 1 error in 1.23s ====================""",
     {"passed": 7, "failed": 2, "errors": 1, "collected": 10}),
]

def _parse_pytest(text: str) -> dict:
    """Parse pytest output for test statistics."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    # The summary line contains timing info, so we search for that pattern
    # Search for all matches and find the one with timing info
    for m in re.finditer(r"=+\s+(.*?)\s+=+", text):
        summary = m.group(1)
        # Check if this is the summary line (contains "in Xs")
        if re.search(r"\s+in\s+[\d.]+s", summary):
            # Parse the summary line
            for key in stats:
                mm = re.search(fr"(\d+)\s+{key}", summary)
                if mm:
                    stats[key] = int(mm.group(1))
            break
    
    # Also check for "collected X items" to ensure tests ran
    collected = re.search(r"collected\s+(\d+)\s+item", text)
    if collected:
        stats["collected"] = int(collected.group(1))
        
        # If we collected tests but parsed stats show 0 for everything,
        # and we see "X passed in" pattern, it means all tests passed
        if stats["passed"] == 0 and stats["failed"] == 0 and stats["errors"] == 0:
            all_passed = re.search(r"(\d+)\s+passed\s+in\s+[\d.]+s", text)
            if all_passed:
                stats["passed"] = int(all_passed.group(1))
    
    return stats

# Test all cases
print("Testing fixed _parse_pytest function:\n")
for i, (output, expected) in enumerate(test_cases, 1):
    result = _parse_pytest(output)
    passed = result == expected
    print(f"Test case {i}: {'PASS' if passed else 'FAIL'}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    if not passed:
        print(f"  Mismatch!")
    print()

# Test with the problematic output that was returning all zeros
print("\nTesting the specific problematic case:")
problematic = """-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
                                DO *NOT* COMMIT!                                
======================== 1 failed, 96 warnings in 0.15s ========================


ERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)"""

result = _parse_pytest(problematic)
print(f"Result: {result}")
print(f"Expected: failed=1, passed=0, errors=0")
print(f"Correct: {result['failed'] == 1 and result['passed'] == 0 and result['errors'] == 0}")
