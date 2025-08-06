#!/usr/bin/env python3
"""Evaluate SWE-Bench predictions using the official harness."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_swebench_evaluation(
    predictions_file: str,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    max_workers: int = 4,
    timeout: int = 1800,
    run_id: Optional[str] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run SWE-Bench evaluation on predictions file.

    Args:
        predictions_file: Path to JSONL file with predictions
        dataset_name: HuggingFace dataset name
        max_workers: Number of parallel workers
        timeout: Timeout per instance in seconds
        run_id: Custom run identifier
        verbose: Enable verbose logging

    Returns:
        Evaluation results dict
    """

    predictions_path = Path(predictions_file)
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_file}")

    # Load predictions to get run info
    predictions = []
    with open(predictions_path, "r") as f:
        for line in f:
            predictions.append(json.loads(line.strip()))

    if not predictions:
        raise ValueError("No predictions found in file")

    model_name = predictions[0].get("model", "unknown")
    if not run_id:
        run_id = f"{model_name}-eval"

    logger.info("Starting SWE-Bench evaluation...")
    logger.info(f"Predictions file: {predictions_file}")
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Predictions: {len(predictions)}")
    logger.info(f"Max workers: {max_workers}")
    logger.info(f"Run ID: {run_id}")

    # Create results directory
    results_dir = predictions_path.parent / "evaluation_results"
    results_dir.mkdir(exist_ok=True)

    # Run SWE-Bench evaluation with absolute path
    cmd = [
        "python",
        "-m",
        "swebench.harness.run_evaluation",
        "--predictions_path",
        str(predictions_path.absolute()),
        "--max_workers",
        str(max_workers),
        "--timeout",
        str(timeout),
        "--run_id",
        run_id,
        "--dataset_name",
        dataset_name,
    ]

    # Note: --verbose not supported by swebench harness

    logger.info(f"Running evaluation command: {' '.join(cmd)}")

    try:
        # Run evaluation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout * len(predictions) + 300,  # Extra time for setup
            cwd=results_dir,
        )

        if result.returncode != 0:
            logger.error(f"Evaluation failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "run_id": run_id,
                "total_predictions": len(predictions),
            }

        logger.info("Evaluation completed successfully!")
        logger.info(f"STDOUT: {result.stdout}")

        # Parse results
        evaluation_results = parse_evaluation_results(results_dir, run_id)
        evaluation_results.update(
            {
                "success": True,
                "run_id": run_id,
                "total_predictions": len(predictions),
                "model": model_name,
                "dataset": dataset_name,
            }
        )

        return evaluation_results

    except subprocess.TimeoutExpired:
        logger.error(
            f"Evaluation timed out after {timeout * len(predictions) + 300} seconds"
        )
        return {
            "success": False,
            "error": "Evaluation timed out",
            "run_id": run_id,
            "total_predictions": len(predictions),
        }

    except Exception as e:
        logger.error(f"Evaluation failed with exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id,
            "total_predictions": len(predictions),
        }


def parse_evaluation_results(results_dir: Path, run_id: str) -> Dict[str, Any]:
    """Parse evaluation results from SWE-Bench output files."""

    # Look for results files
    results_files = list(results_dir.glob(f"*{run_id}*results*.json"))

    if not results_files:
        logger.warning(f"No results files found for run_id {run_id}")
        return {"resolved": 0, "total": 0, "success_rate": 0.0}

    # Use the most recent results file
    results_file = max(results_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Parsing results from: {results_file}")

    try:
        with open(results_file, "r") as f:
            results = json.load(f)

        # Extract key metrics
        resolved = len([r for r in results.values() if r.get("resolved", False)])
        total = len(results)
        success_rate = resolved / total if total > 0 else 0.0

        return {
            "resolved": resolved,
            "total": total,
            "success_rate": success_rate,
            "detailed_results": results,
            "results_file": str(results_file),
        }

    except Exception as e:
        logger.error(f"Failed to parse results file {results_file}: {e}")
        return {"resolved": 0, "total": 0, "success_rate": 0.0}


def quick_validate_predictions(
    predictions_file: str, sample_size: int = 3
) -> Dict[str, Any]:
    """Quick validation by manually checking a few predictions.

    This is faster than full SWE-Bench evaluation for debugging.
    """

    predictions_path = Path(predictions_file)
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_file}")

    # Load predictions
    predictions = []
    with open(predictions_path, "r") as f:
        for line in f:
            predictions.append(json.loads(line.strip()))

    if not predictions:
        raise ValueError("No predictions found in file")

    # Take sample
    sample_predictions = predictions[:sample_size]
    logger.info(f"Quick validation of {len(sample_predictions)} predictions...")

    validation_results = []

    for pred in sample_predictions:
        instance_id = pred["instance_id"]
        prediction = pred["prediction"]

        logger.info(f"Validating {instance_id}...")

        # Basic validation checks
        result = {
            "instance_id": instance_id,
            "has_prediction": bool(prediction),
            "is_valid_diff": is_valid_diff(prediction),
            "diff_size": len(prediction),
            "prediction_preview": prediction[:200] + "..."
            if len(prediction) > 200
            else prediction,
        }

        validation_results.append(result)

        logger.info(f"  Has prediction: {result['has_prediction']}")
        logger.info(f"  Valid diff: {result['is_valid_diff']}")
        logger.info(f"  Size: {result['diff_size']} chars")

    # Summary
    valid_predictions = sum(1 for r in validation_results if r["is_valid_diff"])
    success_rate = valid_predictions / len(validation_results)

    return {
        "sample_size": len(validation_results),
        "valid_predictions": valid_predictions,
        "success_rate": success_rate,
        "results": validation_results,
    }


def is_valid_diff(diff_text: str) -> bool:
    """Check if text looks like a valid git diff."""

    if not diff_text:
        return False

    # Basic diff format checks
    diff_indicators = ["diff --git", "index ", "@@", "+++", "---", "+", "-"]

    # Should have at least some diff indicators
    indicators_found = sum(1 for indicator in diff_indicators if indicator in diff_text)

    return indicators_found >= 3


def main():
    """CLI interface for evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate SWE-Bench predictions")
    parser.add_argument("predictions_file", help="Path to predictions JSONL file")
    parser.add_argument(
        "--dataset", default="princeton-nlp/SWE-bench_Verified", help="Dataset name"
    )
    parser.add_argument("--workers", type=int, default=4, help="Max workers")
    parser.add_argument(
        "--timeout", type=int, default=1800, help="Timeout per instance"
    )
    parser.add_argument("--run-id", help="Custom run ID")
    parser.add_argument(
        "--quick-validate", action="store_true", help="Quick validation only"
    )
    parser.add_argument(
        "--sample-size", type=int, default=3, help="Sample size for quick validation"
    )

    args = parser.parse_args()

    if args.quick_validate:
        logger.info("Running quick validation...")
        results = quick_validate_predictions(args.predictions_file, args.sample_size)

        print("\nQuick Validation Results:")
        print(f"Sample size: {results['sample_size']}")
        print(f"Valid predictions: {results['valid_predictions']}")
        print(f"Success rate: {results['success_rate']:.1%}")

        for result in results["results"]:
            print(f"\n{result['instance_id']}:")
            print(f"  Valid diff: {result['is_valid_diff']}")
            print(f"  Size: {result['diff_size']} chars")

    else:
        logger.info("Running full SWE-Bench evaluation...")
        results = run_swebench_evaluation(
            args.predictions_file,
            dataset_name=args.dataset,
            max_workers=args.workers,
            timeout=args.timeout,
            run_id=args.run_id,
        )

        print("\nEvaluation Results:")
        print(f"Success: {results['success']}")
        print(f"Run ID: {results['run_id']}")

        if results["success"]:
            print(f"Resolved: {results.get('resolved', 0)}")
            print(f"Total: {results.get('total', 0)}")
            print(f"Success Rate: {results.get('success_rate', 0.0):.1%}")
        else:
            print(f"Error: {results.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
