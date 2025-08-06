#!/usr/bin/env python3
"""Extract unique repo@commit pairs from SWE-Bench instances."""

import json
from pathlib import Path
from collections import defaultdict

def main():
    instances_file = Path("swe_bench_instances.jsonl")
    
    # Track unique combinations
    repo_commits = defaultdict(set)
    
    # Read all instances
    with open(instances_file, 'r') as f:
        for line in f:
            instance = json.loads(line)
            repo = instance['repo']
            base_commit = instance['base_commit']
            env_commit = instance.get('environment_setup_commit', base_commit)
            
            # Add both commits
            repo_commits[repo].add(base_commit)
            if env_commit != base_commit:
                repo_commits[repo].add(env_commit)
    
    # Print summary
    total_repos = len(repo_commits)
    total_commits = sum(len(commits) for commits in repo_commits.values())
    
    print(f"Found {total_repos} unique repositories")
    print(f"Found {total_commits} unique repo@commit combinations")
    print("\nBreakdown by repository:")
    
    for repo, commits in sorted(repo_commits.items()):
        print(f"  {repo}: {len(commits)} commits")
    
    # Write to JSON for other scripts
    output = []
    for repo, commits in repo_commits.items():
        for commit in commits:
            output.append({"repo": repo, "commit": commit})
    
    with open("artifacts/repo_commits.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nWrote {len(output)} repo@commit pairs to artifacts/repo_commits.json")

if __name__ == "__main__":
    main()