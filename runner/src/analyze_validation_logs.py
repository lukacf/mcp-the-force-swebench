#!/usr/bin/env python3
"""Analyze validation logs to generate summary."""

import re
import json
from collections import defaultdict, Counter
from datetime import datetime

def analyze_logs():
    # Read logs
    all_results = []
    
    # Process original validation log
    if os.path.exists('parallel_validation.log'):
        with open('parallel_validation.log', 'r') as f:
            for line in f:
                if 'PASSED' in line or 'FAILED' in line:
                    # Extract instance info
                    match = re.search(r'\[(\d+)/\d+\] (\S+) (PASSED|FAILED)', line)
                    if match:
                        instance_id = match.group(2)
                        status = match.group(3)
                        all_results.append({
                            'instance_id': instance_id,
                            'status': status,
                            'source': 'original_run'
                        })
    
    # Process resume validation log
    if os.path.exists('resume_validation.out'):
        with open('resume_validation.out', 'r') as f:
            for line in f:
                if 'PASSED' in line or 'FAILED' in line:
                    # Extract instance info
                    match = re.search(r'\[(\d+)/\d+\] (\S+) (PASSED|FAILED)', line)
                    if match:
                        instance_id = match.group(2)
                        status = match.group(3)
                        # Don't duplicate if already processed
                        if not any(r['instance_id'] == instance_id for r in all_results):
                            all_results.append({
                                'instance_id': instance_id,
                                'status': status,
                                'source': 'resume_run'
                            })
    
    # Analyze results
    total = len(all_results)
    passed = sum(1 for r in all_results if r['status'] == 'PASSED')
    failed = sum(1 for r in all_results if r['status'] == 'FAILED')
    
    # Group by repository
    by_repo = defaultdict(lambda: {'passed': 0, 'failed': 0, 'total': 0})
    for result in all_results:
        repo = result['instance_id'].split('__')[0].replace('_', '/')
        by_repo[repo]['total'] += 1
        if result['status'] == 'PASSED':
            by_repo[repo]['passed'] += 1
        else:
            by_repo[repo]['failed'] += 1
    
    # Create summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_instances_processed': total,
        'passed': passed,
        'failed': failed,
        'success_rate': passed / total * 100 if total > 0 else 0,
        'by_repository': dict(by_repo),
        'passed_instances': [r['instance_id'] for r in all_results if r['status'] == 'PASSED']
    }
    
    # Print summary
    print(f"SWE-Bench Validation Summary")
    print("=" * 70)
    print(f"Total instances processed: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"\nResults by repository:")
    
    for repo, stats in sorted(by_repo.items()):
        rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {repo:30} {stats['passed']:3}/{stats['total']:3} passed ({rate:5.1f}%)")
    
    print(f"\nPassed instances:")
    for instance in summary['passed_instances']:
        print(f"  - {instance}")
    
    # Save summary
    with open('validation_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary

if __name__ == '__main__':
    import os
    analyze_logs()