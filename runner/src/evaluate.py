#!/usr/bin/env python3
"""Evaluate SWE-Bench predictions using the official harness with sophisticated analysis."""

import json
import logging
import subprocess
import shutil
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_run_directory(run_name: Optional[str] = None, base_dir: str = "runs") -> Optional[Path]:
    """Find run directory by name or get latest."""
    
    base_path = Path(base_dir)
    
    if not base_path.exists():
        logger.error(f"Runs directory not found: {base_dir}")
        return None
    
    if run_name:
        # Look for specific run
        run_dir = base_path / run_name
        if run_dir.exists():
            return run_dir
        else:
            logger.error(f"Run not found: {run_name}")
            return None
    
    else:
        # Find latest run
        run_dirs = [d for d in base_path.iterdir() 
                   if d.is_dir() and d.name.startswith("run-")]
        
        if not run_dirs:
            logger.error("No runs found")
            return None
        
        # Sort by modification time (most recent first)
        latest_dir = max(run_dirs, key=lambda d: d.stat().st_mtime)
        logger.info(f"Using latest run: {latest_dir.name}")
        return latest_dir


def setup_evaluation_directory(run_name: str) -> Path:
    """Create evaluation directory structure."""
    
    eval_base = Path("evaluations")
    eval_base.mkdir(exist_ok=True)
    
    eval_dir = eval_base / run_name
    eval_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (eval_dir / "instance_results").mkdir(exist_ok=True)
    (eval_dir / "swebench_logs").mkdir(exist_ok=True)
    
    return eval_dir


def load_run_data(run_dir: Path) -> Dict[str, Any]:
    """Load run summary and instance data."""
    
    # Load run summary
    summary_file = run_dir / "run_summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"Run summary not found: {summary_file}")
    
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    # Load all instance results
    instance_files = sorted(run_dir.glob("instance-*.json"))
    instances = []
    
    for instance_file in instance_files:
        with open(instance_file, 'r') as f:
            instance_data = json.load(f)
            instances.append(instance_data)
    
    summary['instances_data'] = instances
    return summary


def ensure_predictions_file(run_dir: Path) -> Path:
    """Ensure predictions.jsonl exists with proper SWE-Bench format."""
    
    predictions_file = run_dir / "predictions_swebench.jsonl"
    
    if predictions_file.exists():
        logger.info(f"Using existing predictions file: {predictions_file}")
        return predictions_file
    
    logger.info("Generating SWE-Bench compatible predictions file...")
    
    # Load instance files and create predictions
    instance_files = sorted(run_dir.glob("instance-*.json"))
    predictions = []
    
    for instance_file in instance_files:
        with open(instance_file, 'r') as f:
            result = json.load(f)
        
        if result['success'] and result.get('prediction'):
            # Clean the prediction - remove markdown formatting
            patch = result['prediction']
            if patch.startswith('```diff\n'):
                patch = patch[8:]
            if patch.endswith('\n```'):
                patch = patch[:-4]
            elif patch.endswith('```'):
                patch = patch[:-3]
            
            # Validate patch format
            if validate_patch_format(patch, result['instance_id']):
                prediction = {
                    "instance_id": result['instance_id'],
                    "model_name_or_path": result['model'],
                    "model_patch": patch.strip()  # SWE-Bench expects 'model_patch'
                }
                predictions.append(prediction)
            else:
                logger.warning(f"Skipping {result['instance_id']} - invalid patch format")
    
    # Save predictions file
    with open(predictions_file, 'w') as f:
        for pred in predictions:
            f.write(json.dumps(pred) + '\n')
    
    logger.info(f"Generated {len(predictions)} valid predictions in {predictions_file}")
    return predictions_file


def validate_patch_format(patch: str, instance_id: str) -> bool:
    """Validate that patch is in proper git diff format."""
    
    if not patch or not patch.strip():
        return False
    
    # Must contain diff header and hunks
    has_diff_header = 'diff --git' in patch
    has_file_headers = ('---' in patch and '+++' in patch)
    has_hunks = '@@' in patch or 'new file mode' in patch or 'deleted file mode' in patch
    
    if not (has_diff_header and (has_file_headers or 'new file mode' in patch)):
        logger.debug(f"Patch validation failed for {instance_id}: missing required headers")
        return False
    
    return True


def run_swebench_evaluation(
    predictions_file: Path,
    run_name: str,
    eval_dir: Path,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    max_workers: int = 2,  # Reduced default to avoid resource issues
    timeout: int = 900     # Reduced timeout per instance
) -> Dict[str, Any]:
    """Run SWE-Bench evaluation harness and capture detailed results."""
    
    logger.info("Starting SWE-Bench evaluation...")
    logger.info(f"Predictions file: {predictions_file}")
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Max workers: {max_workers}")
    logger.info(f"Evaluation directory: {eval_dir}")
    
    # Setup evaluation working directory
    eval_work_dir = eval_dir / "swebench_logs"
    
    # Run SWE-Bench evaluation
    cmd = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--predictions_path", str(predictions_file.absolute()),
        "--max_workers", str(max_workers),
        "--timeout", str(timeout),
        "--run_id", f"{run_name}-eval",
        "--dataset_name", dataset_name,
    ]
    
    logger.info(f"Running evaluation command...")
    logger.debug(f"Command: {' '.join(cmd)}")
    
    try:
        # Load predictions to get count
        predictions = []
        with open(predictions_file, 'r') as f:
            for line in f:
                predictions.append(json.loads(line.strip()))
        
        # Run evaluation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout * len(predictions) + 600,  # Extra time for setup
            cwd=eval_work_dir
        )
        
        # Save execution logs
        log_file = eval_work_dir / "harness_execution.log"
        with open(log_file, 'w') as f:
            f.write(f"Command: {' '.join(cmd)}\n\n")
            f.write(f"Return code: {result.returncode}\n\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
        
        if result.returncode != 0:
            logger.error(f"Evaluation failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "run_name": run_name,
                "total_predictions": len(predictions)
            }
        
        logger.info("Evaluation completed successfully!")
        logger.info(f"STDOUT: {result.stdout}")
        
        # Parse and process detailed results
        evaluation_results = parse_detailed_evaluation_results(eval_work_dir, f"{run_name}-eval", eval_dir)
        evaluation_results.update({
            "success": True,
            "run_name": run_name,
            "total_predictions": len(predictions),
            "dataset": dataset_name,
            "evaluation_timestamp": datetime.now().isoformat(),
            "command": ' '.join(cmd),
            "execution_log": str(log_file)
        })
        
        return evaluation_results
        
    except subprocess.TimeoutExpired:
        logger.error(f"Evaluation timed out")
        return {
            "success": False,
            "error": "Evaluation timed out",
            "run_name": run_name,
            "total_predictions": len(predictions) if 'predictions' in locals() else 0
        }
    
    except Exception as e:
        logger.error(f"Evaluation failed with exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "run_name": run_name,
            "total_predictions": len(predictions) if 'predictions' in locals() else 0
        }


def parse_detailed_evaluation_results(swebench_dir: Path, run_id: str, eval_dir: Path) -> Dict[str, Any]:
    """Parse evaluation results and create detailed individual instance analyses."""
    
    # Look for results files
    results_files = list(swebench_dir.glob(f"*{run_id}*results*.json"))
    
    if not results_files:
        logger.warning(f"No results files found for run_id {run_id}")
        return {"resolved": 0, "total": 0, "success_rate": 0.0}
    
    # Use the most recent results file
    results_file = max(results_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Parsing results from: {results_file}")
    
    try:
        with open(results_file, 'r') as f:
            raw_results = json.load(f)
        
        # Process individual instance results
        individual_results = []
        repository_stats = defaultdict(lambda: {"total": 0, "resolved": 0, "failed": 0})
        error_categories = Counter()
        execution_times = []
        
        instance_results_dir = eval_dir / "instance_results"
        
        for instance_id, result_data in raw_results.items():
            # Extract detailed information
            resolved = result_data.get("resolved", False)
            
            # Categorize errors
            error_category = categorize_error(result_data)
            if not resolved:
                error_categories[error_category] += 1
            
            # Extract repository info
            repo_name = instance_id.split("__")[0] if "__" in instance_id else "unknown"
            repository_stats[repo_name]["total"] += 1
            if resolved:
                repository_stats[repo_name]["resolved"] += 1
            else:
                repository_stats[repo_name]["failed"] += 1
            
            # Create detailed instance result
            instance_result = {
                "instance_id": instance_id,
                "repository": repo_name,
                "resolved": resolved,
                "error_category": error_category,
                "evaluation_timestamp": datetime.now().isoformat(),
                "raw_result": result_data
            }
            
            # Extract execution details if available
            if "test_output" in result_data:
                instance_result["test_output"] = result_data["test_output"]
            if "install_output" in result_data:
                instance_result["install_output"] = result_data["install_output"]
            if "apply_patch_output" in result_data:
                instance_result["apply_patch_output"] = result_data["apply_patch_output"]
            
            individual_results.append(instance_result)
            
            # Save individual instance result
            instance_file = instance_results_dir / f"{instance_id}-eval.json"
            with open(instance_file, 'w') as f:
                json.dump(instance_result, f, indent=2)
        
        # Calculate overall metrics
        resolved_count = len([r for r in individual_results if r["resolved"]])
        total_count = len(individual_results)
        success_rate = resolved_count / total_count if total_count > 0 else 0.0
        
        # Create repository breakdown
        repo_breakdown = {}
        for repo, stats in repository_stats.items():
            repo_breakdown[repo] = {
                "total_instances": stats["total"],
                "resolved_instances": stats["resolved"],
                "failed_instances": stats["failed"],
                "success_rate": stats["resolved"] / stats["total"] if stats["total"] > 0 else 0.0
            }
        
        # Save repository breakdown
        repo_file = eval_dir / "repository_breakdown.json"
        with open(repo_file, 'w') as f:
            json.dump(repo_breakdown, f, indent=2)
        
        # Create error analysis
        error_analysis = {
            "total_failures": sum(error_categories.values()),
            "error_breakdown": dict(error_categories),
            "most_common_errors": error_categories.most_common(5)
        }
        
        # Save error analysis
        error_file = eval_dir / "error_analysis.json"
        with open(error_file, 'w') as f:
            json.dump(error_analysis, f, indent=2)
        
        return {
            "resolved": resolved_count,
            "total": total_count,
            "success_rate": success_rate,
            "repository_breakdown": repo_breakdown,
            "error_analysis": error_analysis,
            "individual_results": individual_results,
            "results_file": str(results_file),
            "individual_results_dir": str(instance_results_dir)
        }
        
    except Exception as e:
        logger.error(f"Failed to parse results file {results_file}: {e}")
        return {"resolved": 0, "total": 0, "success_rate": 0.0}


def categorize_error(result_data: Dict[str, Any]) -> str:
    """Categorize the type of error from SWE-Bench result data."""
    
    if result_data.get("resolved", False):
        return "success"
    
    # Check for different types of failures
    test_output = result_data.get("test_output", "").lower()
    install_output = result_data.get("install_output", "").lower()
    apply_patch_output = result_data.get("apply_patch_output", "").lower()
    
    # Patch application failures
    if "failed" in apply_patch_output or "error" in apply_patch_output:
        return "patch_application_failure"
    
    # Installation/setup failures
    if "error" in install_output or "failed" in install_output:
        return "installation_failure"
    
    # Test execution failures
    if "failed" in test_output:
        return "test_failure"
    
    # Timeout
    if "timeout" in test_output or result_data.get("timed_out", False):
        return "timeout"
    
    # Other/unknown
    return "unknown_failure"


def save_comprehensive_evaluation_summary(eval_dir: Path, eval_results: Dict[str, Any], run_data: Dict[str, Any]):
    """Save comprehensive evaluation summary with all analysis."""
    
    summary = {
        "evaluation_metadata": {
            "run_name": eval_results["run_name"],
            "evaluation_timestamp": eval_results["evaluation_timestamp"],
            "dataset": eval_results.get("dataset", "unknown"),
            "total_predictions": eval_results["total_predictions"]
        },
        
        "generation_results": {
            "model": run_data.get("model", "unknown"),
            "with_mcp": run_data.get("with_mcp", False),
            "total_instances": run_data.get("total_instances", 0),
            "successful_predictions": run_data.get("successful_predictions", 0),
            "generation_success_rate": run_data.get("success_rate", 0.0)
        },
        
        "evaluation_results": {
            "total_evaluated": eval_results["total"],
            "resolved_instances": eval_results["resolved"],
            "failed_instances": eval_results["total"] - eval_results["resolved"],
            "swe_bench_success_rate": eval_results["success_rate"],
            "repository_breakdown": eval_results.get("repository_breakdown", {}),
            "error_analysis": eval_results.get("error_analysis", {})
        },
        
        "performance_analysis": {
            "generation_vs_evaluation": {
                "predictions_generated": run_data.get("successful_predictions", 0),
                "predictions_evaluated": eval_results["total"],
                "evaluation_coverage": eval_results["total"] / run_data.get("successful_predictions", 1)
            },
            "success_funnel": {
                "total_instances": run_data.get("total_instances", 0),
                "successful_generation": run_data.get("successful_predictions", 0),
                "successful_evaluation": eval_results["resolved"],
                "final_success_rate": eval_results["resolved"] / run_data.get("total_instances", 1)
            }
        },
        
        "files_generated": {
            "evaluation_summary": "evaluation_summary.json",
            "repository_breakdown": "repository_breakdown.json", 
            "error_analysis": "error_analysis.json",
            "individual_results_directory": "instance_results/",
            "swebench_logs_directory": "swebench_logs/"
        }
    }
    
    summary_file = eval_dir / "evaluation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Comprehensive evaluation summary saved to: {summary_file}")


def quick_validate_predictions(predictions_file: Path, sample_size: int = 3) -> Dict[str, Any]:
    """Quick validation by checking prediction format."""
    
    predictions = []
    with open(predictions_file, 'r') as f:
        for line in f:
            predictions.append(json.loads(line.strip()))
    
    # Take sample
    sample_predictions = predictions[:sample_size]
    logger.info(f"Quick validation of {len(sample_predictions)} predictions...")
    
    validation_results = []
    
    for pred in sample_predictions:
        instance_id = pred['instance_id']
        prediction = pred['prediction']
        
        # Basic validation checks
        result = {
            "instance_id": instance_id,
            "has_prediction": bool(prediction),
            "is_valid_diff": is_valid_diff(prediction),
            "diff_size": len(prediction),
        }
        
        validation_results.append(result)
    
    # Summary
    valid_predictions = sum(1 for r in validation_results if r['is_valid_diff'])
    success_rate = valid_predictions / len(validation_results)
    
    return {
        "sample_size": len(validation_results),
        "valid_predictions": valid_predictions,
        "success_rate": success_rate,
        "results": validation_results
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


def list_available_runs(base_dir: str = "runs") -> List[Dict[str, Any]]:
    """List all available runs with summary info."""
    
    base_path = Path(base_dir)
    
    if not base_path.exists():
        return []
    
    runs = []
    run_dirs = [d for d in base_path.iterdir() 
               if d.is_dir() and d.name.startswith("run-")]
    
    for run_dir in sorted(run_dirs, key=lambda d: d.stat().st_mtime, reverse=True):
        summary_file = run_dir / "run_summary.json"
        
        if summary_file.exists():
            try:
                with open(summary_file, 'r') as f:
                    summary = json.load(f)
                
                # Check if evaluation exists
                eval_dir = Path("evaluations") / run_dir.name
                has_evaluation = (eval_dir / "evaluation_summary.json").exists()
                
                runs.append({
                    "run_name": run_dir.name,
                    "model": summary.get("model", "unknown"),
                    "total_instances": summary.get("total_instances", 0),
                    "successful_predictions": summary.get("successful_predictions", 0),
                    "generation_success_rate": summary.get("success_rate", 0.0),
                    "timestamp": summary.get("timestamp", "unknown"),
                    "has_evaluation": has_evaluation,
                    "directory": str(run_dir)
                })
            except:
                runs.append({
                    "run_name": run_dir.name,
                    "model": "unknown",
                    "total_instances": 0,
                    "successful_predictions": 0,
                    "generation_success_rate": 0.0,
                    "timestamp": "unknown",
                    "has_evaluation": False,
                    "directory": str(run_dir)
                })
    
    return runs


def print_detailed_results(eval_dir: Path):
    """Print detailed evaluation results."""
    
    summary_file = eval_dir / "evaluation_summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        
        print(f"\n{'='*80}")
        print("DETAILED EVALUATION RESULTS")
        print(f"{'='*80}")
        
        gen = summary["generation_results"]
        eval_res = summary["evaluation_results"]
        perf = summary["performance_analysis"]
        
        print(f"Model: {gen['model']}")
        print(f"MCP Enabled: {gen['with_mcp']}")
        print(f"Total Instances: {gen['total_instances']}")
        print(f"Generation Success: {gen['successful_predictions']}/{gen['total_instances']} ({gen['generation_success_rate']:.1%})")
        print(f"Evaluation Success: {eval_res['resolved_instances']}/{eval_res['total_evaluated']} ({eval_res['swe_bench_success_rate']:.1%})")
        print(f"Overall Success: {perf['success_funnel']['successful_evaluation']}/{perf['success_funnel']['total_instances']} ({perf['success_funnel']['final_success_rate']:.1%})")
        
        print(f"\n{'='*50}")
        print("REPOSITORY BREAKDOWN")
        print(f"{'='*50}")
        
        repo_breakdown = eval_res.get("repository_breakdown", {})
        if repo_breakdown:
            print(f"{'Repository':<20} {'Total':<6} {'Resolved':<9} {'Rate':<6}")
            print("-" * 50)
            for repo, stats in sorted(repo_breakdown.items(), key=lambda x: x[1]['success_rate'], reverse=True):
                print(f"{repo:<20} {stats['total_instances']:<6} {stats['resolved_instances']:<9} {stats['success_rate']:.1%}")
        
        print(f"\n{'='*50}")
        print("ERROR ANALYSIS")
        print(f"{'='*50}")
        
        error_analysis = eval_res.get("error_analysis", {})
        if error_analysis.get("error_breakdown"):
            for error_type, count in error_analysis["error_breakdown"].items():
                print(f"{error_type.replace('_', ' ').title()}: {count}")
        
        print(f"\n🎯 Target: 70%+ (Current SOTA: 75.20%)")
        
        if eval_res['swe_bench_success_rate'] >= 0.70:
            print(f"🎉 EXCELLENT! Achieved target performance!")
        elif eval_res['swe_bench_success_rate'] >= 0.60:
            print(f"🔥 Very good performance, close to target!")
        elif eval_res['swe_bench_success_rate'] >= 0.50:
            print(f"✅ Good performance, room for improvement")
        else:
            print(f"📈 Performance needs improvement")


def main():
    """CLI interface for evaluation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate SWE-Bench predictions")
    parser.add_argument("--run", help="Run name to evaluate (latest if not specified)")
    parser.add_argument("--runs-dir", default="runs", help="Runs directory")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Verified", help="Dataset name")
    parser.add_argument("--workers", type=int, default=4, help="Max workers")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout per instance")
    parser.add_argument("--quick-validate", action="store_true", help="Quick validation only")
    parser.add_argument("--list-runs", action="store_true", help="List available runs")
    parser.add_argument("--sample-size", type=int, default=3, help="Sample size for quick validation")
    parser.add_argument("--show-details", action="store_true", help="Show detailed results from existing evaluation")
    
    args = parser.parse_args()
    
    if args.list_runs:
        runs = list_available_runs(args.runs_dir)
        
        if not runs:
            print("No runs found.")
            return
        
        print(f"\nAvailable runs ({len(runs)}):")
        print("-" * 100)
        print(f"{'Run Name':<15} {'Model':<20} {'Gen Success':<12} {'Total':<6} {'Rate':<6} {'Evaluated':<10} {'Timestamp'}")
        print("-" * 100)
        
        for run in runs:
            eval_status = "✅" if run['has_evaluation'] else "❌"
            print(f"{run['run_name']:<15} {run['model']:<20} {run['successful_predictions']:<12} {run['total_instances']:<6} {run['generation_success_rate']:.1%:<6} {eval_status:<10} {run['timestamp'][:19]}")
        
        return
    
    # Find run directory
    run_dir = find_run_directory(args.run, args.runs_dir)
    if not run_dir:
        return
    
    run_name = run_dir.name
    logger.info(f"Processing run: {run_name}")
    
    # Setup evaluation directory
    eval_dir = setup_evaluation_directory(run_name)
    
    # Show details if requested
    if args.show_details:
        print_detailed_results(eval_dir)
        return
    
    try:
        # Load run data
        run_data = load_run_data(run_dir)
        
        print(f"\nRun Summary:")
        print(f"Run: {run_name}")
        print(f"Model: {run_data.get('model', 'unknown')}")
        print(f"Total instances: {run_data.get('total_instances', 0)}")
        print(f"Successful predictions: {run_data.get('successful_predictions', 0)}")
        print(f"Generation success rate: {run_data.get('success_rate', 0.0):.1%}")
        
        # Ensure predictions file exists
        predictions_file = ensure_predictions_file(run_dir)
        
        if args.quick_validate:
            print(f"\n{'='*50}")
            print("Quick Validation...")
            print(f"{'='*50}")
            
            val_results = quick_validate_predictions(predictions_file, args.sample_size)
            
            print(f"Sample size: {val_results['sample_size']}")
            print(f"Valid predictions: {val_results['valid_predictions']}")
            print(f"Validation rate: {val_results['success_rate']:.1%}")
            
            for result in val_results['results']:
                print(f"\n{result['instance_id']}:")
                print(f"  Valid diff: {result['is_valid_diff']}")
                print(f"  Size: {result['diff_size']} chars")
        
        else:
            print(f"\n{'='*50}")
            print("Running SWE-Bench Evaluation...")
            print(f"{'='*50}")
            
            eval_results = run_swebench_evaluation(
                predictions_file,
                run_name,
                eval_dir,
                dataset_name=args.dataset,
                max_workers=args.workers,
                timeout=args.timeout
            )
            
            if eval_results['success']:
                # Save comprehensive evaluation summary
                save_comprehensive_evaluation_summary(eval_dir, eval_results, run_data)
                
                # Print detailed results
                print_detailed_results(eval_dir)
                
            else:
                print(f"Evaluation failed: {eval_results.get('error', 'Unknown error')}")
                print("\nTroubleshooting tips:")
                print("- Check that Docker is running")
                print("- Ensure swebench package is installed: pip install swebench")
                print("- Try with fewer workers: --workers 1")
    
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()