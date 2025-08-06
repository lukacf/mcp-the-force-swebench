# SWE-Bench Runner Makefile
.PHONY: all precache run evaluate clean help

# Default target
all: run

# Help target
help:
	@echo "SWE-Bench Runner - Available targets:"
	@echo "  make precache    - Download git mirrors and commits"
	@echo "  make run         - Run the benchmark (includes caching)"
	@echo "  make evaluate    - Evaluate results"
	@echo "  make clean       - Clean artifacts"
	@echo ""
	@echo "Quick start:"
	@echo "  make run         - This will do everything needed"

# Pre-cache git repositories and commits
precache:
	@echo "🔄 Pre-caching git repositories..."
	python scripts/precache_repos.py

# Run the benchmark with caching
run: precache
	@echo "🚀 Running SWE-Bench..."
	cd src && SWEBENCH_REQUIRE_CACHE=1 python -m dispatcher --workers 4

# Run with custom options
run-sample: precache
	@echo "🧪 Running sample (5 instances)..."
	cd src && SWEBENCH_REQUIRE_CACHE=1 python -m dispatcher --sample 5

# Evaluate results
evaluate:
	@echo "📊 Evaluating results..."
	cd src && python -m evaluate

# Clean all artifacts
clean:
	@echo "🧹 Cleaning artifacts..."
	rm -rf artifacts/cache artifacts/worktrees artifacts/runs artifacts/results

# Clean temporary files only (keep caches)
clean-temp:
	@echo "🧹 Cleaning temporary files..."
	rm -rf artifacts/worktrees artifacts/runs