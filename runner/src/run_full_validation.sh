#!/bin/bash
# Run full validation with all fixes applied

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="validation_full_${TIMESTAMP}.log"
RESULTS_FILE="validation_results_${TIMESTAMP}.json"

echo "Starting full SWE-Bench validation run..."
echo "Log file: $LOG_FILE"
echo "Results will be saved to: $RESULTS_FILE"
echo ""

# Run validation in background
nohup python run_parallel_validation.py > "$LOG_FILE" 2>&1 &
VAL_PID=$!

echo "Validation started with PID: $VAL_PID"
echo "You can monitor progress with: tail -f $LOG_FILE"
echo ""
echo "To check status: ps -p $VAL_PID"
echo "To stop: kill $VAL_PID"
