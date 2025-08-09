#!/usr/bin/env python3
"""
Test just the test extraction logic.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import evaluator

# Test extraction with Django instances
with open('swe_bench_django.jsonl') as f:
    for i, line in enumerate(f):
        if i >= 3:  # Just test first 3
            break
            
        instance = json.loads(line)
        print(f"\n{'='*60}")
        print(f"Instance: {instance['instance_id']}")
        
        test_patch = instance['test_patch']
        
        # Test without workdir (should return directories)
        test_files = evaluator.extract_test_files_from_patch(test_patch)
        print(f"Extracted (no workdir): {test_files}")
        
        # Show what was modified
        modified = []
        for line in test_patch.split('\n'):
            if line.startswith('diff --git a/'):
                parts = line.split()
                if len(parts) >= 3:
                    modified.append(parts[2].replace('a/', ''))
        
        print(f"Modified files: {modified}")
        
        # Check if it's Python files or data files
        has_python = any(f.endswith('.py') for f in modified)
        has_data = any(not f.endswith('.py') for f in modified)
        
        print(f"Has Python test files: {has_python}")
        print(f"Has data files: {has_data}")
        
        if has_data and not has_python:
            print("Strategy: Need to find Python tests in same directory as data files")