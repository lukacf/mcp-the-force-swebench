#!/usr/bin/env python3
"""Fix the parallel validator to correctly interpret test results."""

import re

# Read the parallel validator
with open('parallel_validator.py', 'r') as f:
    content = f.read()

# Fix the logic to correctly determine if tests passed
old_logic = """            # Analyze results
            test_only_passed = result1.get('passed', False)
            with_fix_passed = result2.get('passed', False)"""

new_logic = """            # Analyze results
            # Determine if tests passed based on stats
            stats1 = result1
            stats2 = result2
            
            # Tests pass if there are no failures/errors (and at least some tests ran)
            test_only_passed = (
                stats1.get('failed', 0) == 0 and 
                stats1.get('errors', 0) == 0 and
                (stats1.get('passed', 0) > 0 or stats1.get('collected', 0) > 0)
            )
            with_fix_passed = (
                stats2.get('failed', 0) == 0 and 
                stats2.get('errors', 0) == 0 and
                (stats2.get('passed', 0) > 0 or stats2.get('collected', 0) > 0)
            )"""

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    
    # Also update the stats references in the return dict
    content = content.replace(
        "'stats': result1.get('stats', {})",
        "'stats': result1"
    )
    content = content.replace(
        "'stats': result2.get('stats', {})",
        "'stats': result2"
    )
    
    # Write the fixed version
    with open('parallel_validator_fixed.py', 'w') as f:
        f.write(content)
    
    print("Created parallel_validator_fixed.py with corrected test result interpretation")
    print("\nKey changes:")
    print("1. Tests pass if failed == 0 AND errors == 0")
    print("2. Must have either passed > 0 OR collected > 0 (to handle Django's OK output)")
    print("3. Removed incorrect boolean interpretation of 'passed' field")
else:
    print("Could not find the code to fix. The file may have already been updated.")