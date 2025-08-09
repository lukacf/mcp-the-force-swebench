#!/usr/bin/env python3
"""Fetch SWE-Bench Verified dataset for evaluation."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any

try:
    from datasets import load_dataset
except ImportError:
    print("Installing required packages...")
    os.system("pip install datasets")
    from datasets import load_dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_swe_bench_verified(sample_size: int = None) -> List[Dict[str, Any]]:
    """Fetch SWE-Bench Verified dataset.

    Args:
        sample_size: If provided, return only this many instances for testing

    Returns:
        List of SWE-Bench instances
    """
    logger.info("Loading SWE-Bench Verified dataset...")

    # Load the dataset
    dataset = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    instances = []
    for item in dataset:
        instance = {
            "instance_id": item["instance_id"],
            "problem_statement": item["problem_statement"],
            "repo": item["repo"],
            "base_commit": item["base_commit"],
            "patch": item["patch"],  # The expected solution
            "test_patch": item.get("test_patch", ""),
        }
        instances.append(instance)

        if sample_size and len(instances) >= sample_size:
            break

    logger.info(f"Loaded {len(instances)} instances")
    return instances


def save_instances(
    instances: List[Dict[str, Any]], output_file: str = "swe_bench_instances.jsonl"
):
    """Save instances to JSONL file."""
    output_path = Path(__file__).parent / output_file

    with open(output_path, "w") as f:
        for instance in instances:
            f.write(json.dumps(instance) + "\n")

    logger.info(f"Saved {len(instances)} instances to {output_path}")


def load_instances(
    input_file: str = None,
) -> List[Dict[str, Any]]:
    """Load instances from JSONL file."""
    if input_file is None:
        input_file = "swe_bench_instances.jsonl"
    input_path = Path(__file__).parent / input_file

    if not input_path.exists():
        logger.warning(f"File {input_path} not found. Fetching fresh data...")
        instances = fetch_swe_bench_verified()
        save_instances(instances, input_file)
        return instances

    instances = []
    with open(input_path, "r") as f:
        for line in f:
            instances.append(json.loads(line.strip()))

    logger.info(f"Loaded {len(instances)} instances from {input_path}")
    return instances


def get_sample_instance() -> Dict[str, Any]:
    """Get a single instance for testing."""
    instances = load_instances()
    return instances[0] if instances else None


def main():
    """CLI interface for data fetching."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch SWE-Bench Verified data")
    parser.add_argument(
        "--sample-size", type=int, help="Number of instances to fetch (default: all)"
    )
    parser.add_argument(
        "--output", default="swe_bench_instances.jsonl", help="Output file"
    )
    parser.add_argument(
        "--show-sample", action="store_true", help="Show a sample instance"
    )

    args = parser.parse_args()

    if args.show_sample:
        instance = get_sample_instance()
        if instance:
            print("Sample instance:")
            print(json.dumps(instance, indent=2))
        else:
            print("No instances available")
        return

    instances = fetch_swe_bench_verified(sample_size=args.sample_size)
    save_instances(instances, args.output)

    print("\nDataset summary:")
    print(f"- Total instances: {len(instances)}")
    print(f"- Saved to: {args.output}")

    if instances:
        # Show repo distribution
        repos = {}
        for instance in instances:
            repo = instance["repo"]
            repos[repo] = repos.get(repo, 0) + 1

        print(f"- Unique repositories: {len(repos)}")
        print("- Top repositories:")
        for repo, count in sorted(repos.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {repo}: {count} instances")


if __name__ == "__main__":
    main()
