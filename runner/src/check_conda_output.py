#!/usr/bin/env python3
"""Check how conda run affects output."""

import subprocess

# Run a simple pytest command that will fail
result = subprocess.run(
    ["conda", "run", "-n", "base", "python", "-c", "import sys; print('STDOUT'); print('STDERR', file=sys.stderr); sys.exit(1)"],
    capture_output=True,
    text=True
)

print(f"Exit code: {result.returncode}")
print(f"\nSTDOUT ({len(result.stdout)} chars):")
print(repr(result.stdout))
print(f"\nSTDERR ({len(result.stderr)} chars):")
print(repr(result.stderr))

# Now let's check what conda run does with pytest output
print("\n" + "="*80)
print("Testing conda run with echo commands...")

result2 = subprocess.run(
    ["conda", "run", "-n", "base", "bash", "-c", "echo 'This is stdout'; echo 'This is stderr' >&2; exit 1"],
    capture_output=True,
    text=True
)

print(f"Exit code: {result2.returncode}")
print(f"\nSTDOUT:")
print(repr(result2.stdout))
print(f"\nSTDERR:")
print(repr(result2.stderr))