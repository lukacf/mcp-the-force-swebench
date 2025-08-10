#!/usr/bin/env python3
"""Monitor validation progress and estimate completion time."""

import re
import time
import sys
import os
from datetime import datetime, timedelta

def parse_log_line(line):
    """Parse a validation log line for progress info."""
    match = re.search(r'\[(\d+)/500\] (\S+) (PASSED|FAILED) \(([\d.]+)s\)', line)
    if match:
        completed = int(match.group(1))
        instance_id = match.group(2)
        status = match.group(3)
        duration = float(match.group(4))
        return completed, instance_id, status, duration
    return None

def monitor_validation(log_file):
    """Monitor validation progress from log file."""
    if not os.path.exists(log_file):
        print(f"Error: Log file {log_file} not found")
        return
    
    print(f"Monitoring validation progress from: {log_file}")
    print("Press Ctrl+C to stop monitoring\n")
    
    start_time = None
    last_update = None
    passed = 0
    failed = 0
    total_duration = 0
    
    try:
        with open(log_file, 'r') as f:
            # Move to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    parsed = parse_log_line(line)
                    if parsed:
                        completed, instance_id, status, duration = parsed
                        
                        if not start_time:
                            start_time = datetime.now()
                        
                        if status == "PASSED":
                            passed += 1
                        else:
                            failed += 1
                        
                        total_duration += duration
                        last_update = datetime.now()
                        
                        # Calculate rates and estimates
                        elapsed = (last_update - start_time).total_seconds()
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = 500 - completed
                        eta_seconds = remaining / rate if rate > 0 else 0
                        eta = last_update + timedelta(seconds=eta_seconds)
                        
                        # Calculate pass rate
                        pass_rate = (passed / completed * 100) if completed > 0 else 0
                        
                        # Clear line and print status
                        print(f"\r[{completed}/500] {instance_id} {status} | "
                              f"Pass rate: {pass_rate:.1f}% ({passed}/{completed}) | "
                              f"Rate: {rate:.1f}/s | "
                              f"ETA: {eta.strftime('%H:%M:%S')}", end='', flush=True)
                        
                        # Print summary every 50 instances
                        if completed % 50 == 0:
                            avg_duration = total_duration / completed
                            print(f"\n\n--- Progress Report at {completed}/500 ---")
                            print(f"Passed: {passed}, Failed: {failed}")
                            print(f"Pass rate: {pass_rate:.1f}%")
                            print(f"Average duration: {avg_duration:.1f}s")
                            print(f"Processing rate: {rate:.1f} instances/second")
                            print(f"Estimated completion: {eta.strftime('%Y-%m-%d %H:%M:%S')}")
                            print("-" * 50 + "\n")
                else:
                    time.sleep(0.5)  # Wait for new data
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        if last_update:
            print(f"\nFinal stats:")
            print(f"Completed: {completed}/500")
            print(f"Passed: {passed}, Failed: {failed}")
            print(f"Pass rate: {pass_rate:.1f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        # Find the most recent validation log
        import glob
        logs = sorted(glob.glob("validation_full_*.log"), reverse=True)
        if logs:
            log_file = logs[0]
        else:
            print("No validation log files found.")
            sys.exit(1)
    
    monitor_validation(log_file)
