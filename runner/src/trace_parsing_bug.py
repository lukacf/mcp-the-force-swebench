#!/usr/bin/env python3
"""Trace the parsing bug step by step."""

import re

text = """-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
                                DO *NOT* COMMIT!                                
======================== 1 failed, 96 warnings in 0.15s ========================


ERROR conda.cli.main_run:execute(124): `conda run pytest -v --tb=short --no-header -rN sympy/geometry/tests/test_point.py::test_issue_11617` failed. (See above for error)"""

def _parse_pytest_debug(text: str) -> dict:
    """Parse pytest output for test statistics WITH DEBUG."""
    stats = {"passed": 0, "failed": 0, "errors": 0}
    
    print("Step 1: Looking for summary line...")
    # Look for summary line like "====== 5 failed, 10 passed in 2.34s ======"
    m = re.search(r"=+\s+(.*?)\s+=+", text)
    if m:
        print(f"  Found match: '{m.group(0)}'")
        print(f"  Extracted summary: '{m.group(1)}'")
        summary = m.group(1)
        
        print("\nStep 2: Extracting counts from summary...")
        for key in stats:
            print(f"  Looking for '{key}'...")
            mm = re.search(fr"(\d+)\s+{key}", summary)
            if mm:
                print(f"    Found: {mm.group(0)} -> {mm.group(1)}")
                stats[key] = int(mm.group(1))
            else:
                print(f"    Not found")
    else:
        print("  No match found!")
    
    print(f"\nStep 3: Final stats: {stats}")
    
    # Let's also check what happens with re.findall
    print("\nStep 4: Using findall to see all matches...")
    all_matches = re.findall(r"=+\s+(.*?)\s+=+", text)
    print(f"  All matches: {all_matches}")
    
    # Check if we're matching the right line
    if "1 failed, 96 warnings in 0.15s" in text:
        print("\nStep 5: The summary line IS in the text")
        # Try direct search
        direct = re.search(r"(\d+)\s+failed", text)
        if direct:
            print(f"  Direct search for 'X failed' found: {direct.group(0)}")
    
    return stats

result = _parse_pytest_debug(text)