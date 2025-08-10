#!/usr/bin/env python3
"""Simulate what the tester service is doing."""

import re

# This is the FULL output from pytest
full_output = """============================= test session starts ==============================
platform linux -- Python 3.9.20, pytest-8.4.1, pluggy-1.6.0 -- /opt/miniconda3/envs/testbed/bin/python
cachedir: .pytest_cache
architecture: 64-bit
cache:        yes
ground types: python 

rootdir: /testbed
collecting ... collected 1 item

sympy/geometry/tests/test_point.py::test_issue_11617 FAILED              [100%]

=================================== FAILURES ===================================
_______________________________ test_issue_11617 _______________________________
sympy/geometry/tests/test_point.py:250: in test_issue_11617
    assert p1.distance(p2) == sqrt(5)
E   assert 1 == sqrt(5)
E    +  where 1 = distance(Point2D(2, 0))
E    +    where distance = Point3D(1, 0, 2).distance
E    +  and   sqrt(5) = sqrt(5)
=============================== warnings summary ===============================
[90 warning lines omitted for brevity]
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
                                DO *NOT* COMMIT!                                
======================== 1 failed, 96 warnings in 0.15s ========================"""

# Add conda error to stderr
stderr = "\n\nERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)"

# Combine as tester does
out = full_output + "\n" + stderr

def _parse_pytest(text: str) -> dict:
    """Parse pytest output for test statistics."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    m = re.search(r"=+\s+(.*?)\s+=+", text)
    if m:
        summary = m.group(1)
        for key in stats:
            mm = re.search(fr"(\d+)\s+{key}", summary)
            if mm:
                stats[key] = int(mm.group(1))
    
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

# Test 1: Parse the full output
print("Test 1: Parsing full output")
# Debug the regex
import re
all_matches = re.findall(r"=+\s+(.*?)\s+=+", out)
print(f"All regex matches: {all_matches}")
stats = _parse_pytest(out)
print(f"Stats: {stats}")

# Test 2: Get the tail (last 50 lines)
lines = out.splitlines()
print(f"\nTest 2: Total lines: {len(lines)}")
tail = "\n".join(lines[-50:])
print(f"Tail starts at line {len(lines)-50}")
print(f"First line of tail: {lines[-50] if len(lines) >= 50 else 'N/A'}")
print(f"Summary line position: {[i for i, line in enumerate(lines) if '1 failed, 96 warnings' in line]}")

# Now let's see what happens if we have MORE output
print("\n\nTest 3: What if there's more output after the summary?")
# Add more lines after the summary
extra_output = out + "\n" + "\n".join([f"Extra line {i}" for i in range(100)])
extra_lines = extra_output.splitlines()
print(f"Total lines with extra: {len(extra_lines)}")
tail_extra = "\n".join(extra_lines[-50:])
print(f"Tail contains summary? {'1 failed' in tail_extra}")
stats_extra = _parse_pytest(tail_extra)
print(f"Stats from tail: {stats_extra}")