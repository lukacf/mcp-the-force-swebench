#!/usr/bin/env python3
"""Debug Django evaluation to understand test file extraction."""

import json
import logging
from evaluator import evaluate_patch, extract_test_files_from_patch

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Load Django instance  
with open('test_instance.jsonl', 'r') as f:
    instance = json.loads(f.readline())

print("="*60)
print("DJANGO EVALUATION DEBUG")
print("="*60)

# First, let's see what test files are extracted
print("\n1. Extracting test files from test_patch...")
test_files = extract_test_files_from_patch(instance['test_patch'])
print(f"   Extracted test files: {test_files}")

# Let's manually check what the test_patch contains
print("\n2. Test patch content (first 500 chars):")
print(instance['test_patch'][:500])

# Now let's test with the combined patch
print("\n3. Testing with combined patch (patch + test_patch)...")
combined_patch = instance['patch'] + '\n' + instance['test_patch']
result = evaluate_patch(instance, combined_patch)

print(f"\nResult: {'PASS' if result['passed'] else 'FAIL'}")
print(f"Stats: {result['stats']}")
print(f"Test files run: {result.get('test_files', 'Unknown')}")

# Show output
if result.get('test_output'):
    print("\nTest output (last 30 lines):")
    lines = result['test_output'].split('\n')
    for line in lines[-30:]:
        print(f"  {line}")