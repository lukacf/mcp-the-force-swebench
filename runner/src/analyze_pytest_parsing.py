#!/usr/bin/env python3
"""Analyze the pytest parsing issue in detail."""

import re

# Full pytest output example
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
======================== 1 failed, 96 warnings in 0.15s ========================


ERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)"""

def analyze_regex_behavior():
    """Analyze how the regex behaves with the full output."""
    print("=== Analyzing regex behavior ===")
    
    # The problematic regex
    pattern = r"=+\s+(.*?)\s+=+"
    
    # Find all matches
    all_matches = re.findall(pattern, full_output)
    print(f"\nAll matches found: {len(all_matches)}")
    for i, match in enumerate(all_matches):
        print(f"  Match {i+1}: '{match}'")
    
    # Find match objects to see positions
    print("\n\nMatch positions:")
    for match in re.finditer(pattern, full_output):
        start, end = match.span()
        context_start = max(0, start - 20)
        context_end = min(len(full_output), end + 20)
        context = full_output[context_start:context_end]
        print(f"  Position {start}-{end}: '{match.group(1)}'")
        print(f"    Context: ...{repr(context)}...")
    
    # The issue: re.search returns the FIRST match
    first_match = re.search(pattern, full_output)
    if first_match:
        print(f"\n\nre.search() returns FIRST match: '{first_match.group(1)}'")
    
    # Solution 1: Look for the summary line specifically
    print("\n\n=== Solution 1: Target summary line pattern ===")
    summary_pattern = r"=+\s*([\d\s\w,]+\s+in\s+[\d.]+s)\s*=+"
    summary_match = re.search(summary_pattern, full_output)
    if summary_match:
        print(f"Summary line found: '{summary_match.group(1)}'")
        
        # Parse the summary
        summary = summary_match.group(1)
        stats = {"passed": 0, "failed": 0, "errors": 0}
        for key in stats:
            m = re.search(fr"(\d+)\s+{key}", summary)
            if m:
                stats[key] = int(m.group(1))
        print(f"Parsed stats: {stats}")
    
    # Solution 2: Find all matches and filter for the one with time
    print("\n\n=== Solution 2: Find match containing 'in Xs' ===")
    for match in re.finditer(pattern, full_output):
        content = match.group(1)
        if re.search(r"\s+in\s+[\d.]+s", content):
            print(f"Found summary line: '{content}'")
            break
    
    # Solution 3: Search from the end of the output
    print("\n\n=== Solution 3: Search in reverse (last match) ===")
    all_matches = list(re.finditer(pattern, full_output))
    if all_matches:
        last_match = all_matches[-1]
        print(f"Last match: '{last_match.group(1)}'")
        # Check if it looks like a summary
        if re.search(r"(passed|failed|error|warning)", last_match.group(1), re.I):
            print("  -> This appears to be a summary line")

if __name__ == "__main__":
    analyze_regex_behavior()
