#!/usr/bin/env python3
"""Monitor validation progress in real-time."""

import time
import json
import os
from datetime import datetime

def parse_log_line(line):
    """Parse a validation log line."""
    if 'PASSED' in line or 'FAILED' in line:
        parts = line.strip().split(' - ')
        if len(parts) >= 3:
            # Extract instance number and total
            info_part = parts[2]
            if '[' in info_part and '/' in info_part:
                current = info_part.split('[')[1].split('/')[0]
                total = info_part.split('/')[1].split(']')[0]
                status = 'PASSED' if 'PASSED' in line else 'FAILED'
                return int(current), int(total), status
    return None

def main():
    print("Monitoring SWE-Bench Validation Progress...")
    print("=" * 70)
    
    log_files = ['resume_validation.out', 'validation_resume.log']
    
    last_line_count = 0
    start_time = time.time()
    
    while True:
        # Find the active log file
        active_log = None
        for log_file in log_files:
            if os.path.exists(log_file):
                size = os.path.getsize(log_file)
                if size > 0:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        if len(lines) > last_line_count:
                            active_log = log_file
                            break
        
        if active_log:
            with open(active_log, 'r') as f:
                lines = f.readlines()
            
            # Process new lines
            if len(lines) > last_line_count:
                passed = 0
                failed = 0
                current = 0
                total = 419  # Remaining instances
                
                # Count all results
                for line in lines:
                    result = parse_log_line(line)
                    if result:
                        current, total, status = result
                        if status == 'PASSED':
                            passed += 1
                        else:
                            failed += 1
                
                # Display progress
                elapsed = time.time() - start_time
                rate = current / elapsed if elapsed > 0 and current > 0 else 0
                eta = (total - current) / rate if rate > 0 else 0
                
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Progress: {current}/{total} ({current/total*100:.1f}%) | "
                      f"Passed: {passed} | Failed: {failed} | "
                      f"Rate: {rate:.1f}/s | ETA: {eta/60:.1f}m", end='', flush=True)
                
                last_line_count = len(lines)
                
                # Check if complete
                if 'VALIDATION COMPLETE' in lines[-1] if lines else False:
                    print("\n\nValidation Complete!")
                    # Find and display summary
                    for line in reversed(lines):
                        if 'Valid:' in line:
                            print(line.strip())
                            break
                    break
        
        time.sleep(2)  # Check every 2 seconds

if __name__ == '__main__':
    main()