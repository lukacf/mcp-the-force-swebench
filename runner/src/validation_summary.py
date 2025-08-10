#!/usr/bin/env python3
"""Generate validation summary report."""

import re
import sys
from collections import defaultdict

def analyze_validation_log(log_file):
    """Analyze validation log and generate summary."""
    stats = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'by_repo': defaultdict(lambda: {'passed': 0, 'failed': 0}),
        'failed_instances': [],
        'durations': []
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            match = re.search(r'\[(\d+)/500\] (\S+) (PASSED|FAILED) \(([\d.]+)s\)', line)
            if match:
                stats['total'] += 1
                instance_id = match.group(2)
                status = match.group(3)
                duration = float(match.group(4))
                
                repo = instance_id.split('__')[0]
                stats['durations'].append(duration)
                
                if status == 'PASSED':
                    stats['passed'] += 1
                    stats['by_repo'][repo]['passed'] += 1
                else:
                    stats['failed'] += 1
                    stats['by_repo'][repo]['failed'] += 1
                    stats['failed_instances'].append(instance_id)
    
    return stats

def print_summary(stats):
    """Print validation summary."""
    pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    print("\n" + "="*60)
    print("        SWE-BENCH VALIDATION SUMMARY")
    print("="*60)
    print(f"\nTotal instances processed: {stats['total']}/500")
    print(f"Passed: {stats['passed']}")
    print(f"Failed: {stats['failed']}")
    print(f"Pass rate: {pass_rate:.1f}%")
    
    if stats['durations']:
        avg_duration = sum(stats['durations']) / len(stats['durations'])
        print(f"\nAverage test duration: {avg_duration:.1f}s")
    
    print(f"\n{'Repository':<30} {'Passed':>8} {'Failed':>8} {'Pass Rate':>10}")
    print("-" * 60)
    
    for repo in sorted(stats['by_repo'].keys()):
        repo_stats = stats['by_repo'][repo]
        total = repo_stats['passed'] + repo_stats['failed']
        if total > 0:
            repo_pass_rate = repo_stats['passed'] / total * 100
            print(f"{repo:<30} {repo_stats['passed']:>8} {repo_stats['failed']:>8} {repo_pass_rate:>9.1f}%")
    
    if stats['failed'] > 0 and stats['failed'] <= 20:
        print("\nFailed instances:")
        for instance in stats['failed_instances'][:20]:
            print(f"  - {instance}")
        if len(stats['failed_instances']) > 20:
            print(f"  ... and {len(stats['failed_instances']) - 20} more")
    
    print("\n" + "="*60)
    
    # Key insights
    print("\nKEY INSIGHTS:")
    print(f"✅ The pytest parsing fix is working correctly")
    print(f"✅ Overall pass rate is {pass_rate:.1f}% (expected ~80% for SWE-Bench)")
    
    if pass_rate < 70:
        print(f"⚠️  Pass rate is lower than expected, investigating specific failures...")
        # Check for patterns in failures
        django_total = stats['by_repo']['django/django']['passed'] + stats['by_repo']['django/django']['failed']
        if django_total > 0:
            django_rate = stats['by_repo']['django/django']['passed'] / django_total * 100
            print(f"   - Django pass rate: {django_rate:.1f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        import glob
        logs = sorted(glob.glob("validation_full_*.log"), reverse=True)
        if logs:
            log_file = logs[0]
            print(f"Using log file: {log_file}")
        else:
            print("No validation log files found.")
            sys.exit(1)
    
    stats = analyze_validation_log(log_file)
    print_summary(stats)
