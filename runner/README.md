# SWE-Bench Runner

Efficient parallel execution system for SWE-Bench tasks using git mirrors and worktrees.

## Architecture

- **Git Mirrors**: One bare clone per repository, shared across all workers
- **Worktrees**: Lightweight checkouts for each task
- **Python venvs**: Isolated environments for each checkout
- **Symlinked configs**: Claude/MCP settings available in every worktree

## Quick Start

```bash
# Bootstrap the system
./bootstrap.sh

# Option 1: Simple run (downloads repos on-demand)
cd src
python -m dispatcher --sample 5

# Option 2: Optimized run with pre-caching (recommended)
make run-sample  # Runs 5 instances with full caching
make run         # Full benchmark with caching
```

## Key Features

1. **Efficient Git Operations**
   - Mirrors fetched once, reused for all tasks
   - Worktrees created in milliseconds
   - Automatic cleanup after each task

2. **Proper Python Installation**
   - Each worktree gets its own venv
   - Project installed with `pip install -e .`
   - Test dependencies handled automatically

3. **Test-Driven Iteration**
   - Apply patch → Run tests → Refine
   - Git reset --hard between attempts
   - Clean state guaranteed

4. **Parallel Execution**
   - N workers process tasks concurrently
   - Shared mirrors, isolated worktrees
   - No conflicts or race conditions

5. **Pre-caching Support**
   - Pre-download all git repositories and commits
   - Reduces per-task setup from 60s+ to <5s

## Directory Structure

```
runner/
├── src/                    # Core modules
│   ├── dispatcher.py       # Parallel orchestration
│   ├── worker.py          # Single task execution
│   ├── git_utils.py       # Mirror/worktree management
│   ├── test_runner.py     # Pytest wrapper
│   ├── claude_force_client.py  # Claude interface
│   └── patch_utils.py     # Diff handling
│
├── artifacts/             # Runtime data (git-ignored)
│   ├── cache/            # Git mirrors
│   ├── worktrees/        # Temporary checkouts
│   ├── runs/             # Execution logs
│   └── results/          # Predictions output
│
├── scripts/              # Utility scripts
│   └── precache_repos.py # Pre-download git data
│
├── CLAUDE.md             # Instructions for Claude
├── bootstrap.sh          # Setup script
└── Makefile              # Build automation
```

## Configuration

The system uses configuration from the parent directory:
- `.claude/` - Claude CLI settings
- `.mcp-the-force/` - MCP server config
- `claude_hooks/` - Event hooks

These are symlinked into each worktree automatically.

## Command Options

```bash
python -m dispatcher [options]

Options:
  --workers N        Number of parallel workers (default: 4)
  --sample N         Process only N instances
  --start N          Start from instance N
  --no-mcp          Run without MCP tools
  --iterations N     Max patch attempts per task (default: 5)
  --timeout N        Timeout per iteration in seconds (default: 600)
  --run-name NAME    Custom run identifier

## Performance Optimization

The runner supports git repository caching to reduce per-task overhead:

### Pre-caching (Recommended)

```bash
# Download all repos and commits upfront
make precache     # ~15 min, 2GB

# Or just run everything with:
make run
```

### Benefits

| Without Cache | With Cache | Speedup |
|--------------|------------|---------|
| Git clone: 30-60s | Worktree: <1s | 30-60x |
| **Total speedup** | **Significant** | **30x+** |
```