#!/usr/bin/env python3
"""Test the Django label conversion logic."""

def convert_to_django_test_labels(test_files):
    """Local copy of the conversion function."""
    test_labels = []
    
    for file_path in test_files:
        # Remove .py extension if present
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        
        # Remove trailing slashes
        file_path = file_path.rstrip('/')
        
        # Special handling for paths starting with 'tests/'
        # Django's test runner expects app names, not 'tests.app_name'
        if file_path.startswith('tests/') and '/' not in file_path[6:]:
            # e.g., "tests/validators" -> "validators"
            test_label = file_path[6:]  # Strip 'tests/' prefix
        else:
            # Convert slashes to dots for other paths
            test_label = file_path.replace('/', '.')
        
        # Remove trailing dots
        test_label = test_label.rstrip('.')
        
        test_labels.append(test_label)
    
    return test_labels

# Test cases
test_cases = [
    "tests/validators/",
    "tests/validators",
    "tests/validators/test_ipv4.py",
    "tests/admin_views/",
    "django/core/validators/tests.py",
    "tests/auth_tests/models/custom_user.py"
]

print("Django label conversion test:")
print("="*60)
print(f"{'Input':35} -> {'Output':25}")
print("-"*60)
for test in test_cases:
    result = convert_to_django_test_labels([test])
    print(f"{test:35} -> {result[0]:25}")

print("\nKey insight: 'tests/validators' becomes 'validators' (just the app name)")
print("This should fix the Django test discovery issue!")