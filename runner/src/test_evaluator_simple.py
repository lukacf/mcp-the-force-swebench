#!/usr/bin/env python3
"""
Simple test of the evaluator with a single Django instance.
"""

import json
import logging
from pathlib import Path

from evaluator import extract_test_files_from_patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load a Django instance
django_file = Path("/Users/luka/src/cc/mcp-the-force-swebench/runner/src/swe_bench_django.jsonl")
with open(django_file) as f:
    instance = json.loads(f.readline())

logger.info(f"Testing with instance: {instance['instance_id']}")
logger.info(f"Repo: {instance['repo']}")

# Test 1: Extract test files from test_patch
test_patch = instance.get('test_patch', '')
logger.info(f"\nTest patch length: {len(test_patch)} chars")

test_files = extract_test_files_from_patch(test_patch)
logger.info(f"\nExtracted test files: {test_files}")

# Show a sample of the test patch
logger.info("\nFirst 500 chars of test_patch:")
logger.info(test_patch[:500])

# Test 2: Show what tests SWE-Bench expects us to run
logger.info("\n" + "="*60)
logger.info("SWE-Bench expects us to run ONLY these test files:")
for test_file in test_files:
    logger.info(f"  - {test_file}")

# Test 3: Show the known good patch
patch = instance.get('patch', '')
logger.info(f"\nKnown good patch length: {len(patch)} chars")
logger.info("\nFirst 500 chars of patch:")
logger.info(patch[:500])