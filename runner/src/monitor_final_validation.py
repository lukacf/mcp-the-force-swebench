#!/usr/bin/env python3
"""Monitor the final validation run."""

import time
import re
import os
import glob
import sys

def get_latest_log():
    """Find the most recent validation log."""
    logs = sorted(glob.glob("validation_complete_*.log"), reverse=True)
    if not logs:
        print("No validation logs found.")
        sys.exit(1)
    return logs[0]

def monitor_progress(log_file):
    """Monitor validation progress."""
    print(f"Monitoring: {log_file}")
    print("Press Ctrl+C to stop\n")
    
    last_line = ""
    pass_count = 0
    fail_count = 0
    
    while True:
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Find progress lines
            for line in lines:
                if re.search(r'\[(\d+)/499\]', line):
                    if 'PASSED' in line:
                        pass_count = len([l for l in lines if 'PASSED' in l and '[' in l])
                    elif 'FAILED' in line:
                        fail_count = len([l for l in lines if 'FAILED' in l and '[' in l])
                    last_line = line.strip()
            
            # Check if validation is complete
            if any('VALIDATION COMPLETE' in line for line in lines):
                print("\n" + "="*60)
                print("VALIDATION COMPLETE!")
                # Print final stats
                for line in lines[-50:]:
                    if 'Total:' in line or 'Passed:' in line or 'Failed:' in line or 'Pass rate:' in line:
                        print(line.strip())
                    if 'Repository' in line and 'Pass Rate' in line:
                        # Print the repo summary table
                        idx = lines.index(line)
                        for i in range(idx, min(idx+20, len(lines))):
                            print(lines[i].strip())
                break
            
            # Display current progress
            if last_line:
                total = pass_count + fail_count
                pass_rate = (pass_count / total * 100) if total > 0 else 0
                print(f"\r{last_line} | Overall: {pass_count}/{total} passed ({pass_rate:.1f}%)", end='', flush=True)
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(1)

if __name__ == "__main__":
    log_file = get_latest_log()
    monitor_progress(log_file)
