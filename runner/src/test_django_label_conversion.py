#!/usr/bin/env python3
"""Test the Django test label conversion logic."""

# Copy the fixed conversion function
def convert_to_django_test_labels(test_files):
    """Convert file paths to Django test labels.
    
    Examples:
    - tests/validators/test_ipv4.py -> validators.test_ipv4
    - tests/validators/ -> validators
    - tests/queries/test_qs_combinators.py -> queries.test_qs_combinators
    - django/core/validators/tests.py -> django.core.validators.tests
    """
    test_labels = []
    
    for file_path in test_files:
        # Remove .py extension if present
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        
        # Remove trailing slashes
        file_path = file_path.rstrip('/')
        
        # Special handling for Django's own test suite (paths starting with 'tests/')
        if file_path.startswith('tests/'):
            # For Django core tests, we need to use app-based discovery
            parts = file_path.split('/')
            if len(parts) >= 2:
                # Extract app name and remaining path
                app_name = parts[1]  # e.g., 'queries' from 'tests/queries/test_qs_combinators'
                if len(parts) > 2:
                    # Include test module: queries.test_qs_combinators
                    test_module = '.'.join(parts[2:])
                    test_label = f"{app_name}.{test_module}"
                else:
                    # Just app name: queries
                    test_label = app_name
            else:
                # Shouldn't happen, but fallback
                test_label = file_path.replace('/', '.')
        else:
            # For other paths (django/... etc), use standard conversion
            test_label = file_path.replace('/', '.')
        
        # Remove trailing dots
        test_label = test_label.rstrip('.')
        
        test_labels.append(test_label)
    
    return test_labels


# Test cases
test_cases = [
    # Django core test files
    (["tests/queries/test_qs_combinators.py"], ["queries.test_qs_combinators"]),
    (["tests/validators/test_ipv4.py"], ["validators.test_ipv4"]),
    (["tests/validators/"], ["validators"]),
    (["tests/queries"], ["queries"]),
    
    # Multiple files
    (["tests/queries/test_qs_combinators.py", "tests/queries/models.py"], 
     ["queries.test_qs_combinators", "queries.models"]),
    
    # Non-test paths (django package paths)
    (["django/core/validators/tests.py"], ["django.core.validators.tests"]),
    (["django/db/models/query.py"], ["django.db.models.query"]),
]

print("Testing Django test label conversion:")
print("="*70)

all_passed = True
for test_input, expected in test_cases:
    result = convert_to_django_test_labels(test_input)
    passed = result == expected
    all_passed &= passed
    
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n{status}")
    print(f"  Input:    {test_input}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")

print("\n" + "="*70)
print(f"Overall: {'All tests passed!' if all_passed else 'Some tests failed!'}")