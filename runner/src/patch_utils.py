"""Utilities for handling git patches and diffs."""

import re
import unicodedata
import logging

logger = logging.getLogger(__name__)


def clean_patch(raw: str) -> str:
    """O3's battle-tested patch cleaner - handles all common formatting issues."""
    if not raw or not raw.strip():
        return ""
    
    # Remove markdown code-block fences
    raw = re.sub(r'```diff\s*|```$', '', raw.strip(), flags=re.DOTALL)
    
    # Normalise Unicode – guards against smart quotes
    raw = unicodedata.normalize('NFKC', raw)
    
    # Strip CR characters (Windows line endings)
    raw = raw.replace('\r', '')
    
    # Ensure final newline
    if not raw.endswith('\n'):
        raw += '\n'
    
    return raw


def validate_and_clean_patch(patch: str, instance_id: str) -> str:
    """Apply O3's cleaning and validation pipeline."""
    
    if not patch or not patch.strip():
        return ""
    
    # First, apply O3's proven cleaning
    cleaned = clean_patch(patch)
    
    # O3's automatic guard check
    if not cleaned.startswith('diff --git'):
        logger.warning(f"Patch for {instance_id} doesn't start with 'diff --git'")
        return ""
    
    # Additional validation for essential diff elements
    if not ('@@' in cleaned or 'new file mode' in cleaned or 'deleted file mode' in cleaned):
        logger.warning(f"Patch for {instance_id} missing essential diff elements")
        return ""
    
    return cleaned


def extract_diff_from_response(text: str) -> str:
    """Extract git diff from either XML tags or markdown code blocks."""
    
    # First try: Look for XML tags (case insensitive, multiline)
    xml_pattern = r'<FINAL_DIFF>(.*?)</FINAL_DIFF>'
    xml_match = re.search(xml_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if xml_match:
        diff_content = xml_match.group(1).strip()
        return diff_content
    
    # Second try: Look for markdown code blocks with diff
    # Pattern for ```diff ... ``` blocks
    markdown_pattern = r'```diff\s*\n(.*?)\n```'
    markdown_match = re.search(markdown_pattern, text, re.DOTALL)
    
    if markdown_match:
        diff_content = markdown_match.group(1).strip()
        return diff_content
    
    # Third try: Look for any code block that starts with 'diff --git'
    code_block_pattern = r'```[a-zA-Z]*\s*\n(diff --git.*?)\n```'
    code_match = re.search(code_block_pattern, text, re.DOTALL)
    
    if code_match:
        diff_content = code_match.group(1).strip()
        return diff_content
    
    # Fourth try: Look for raw diff that starts with 'diff --git' (no code blocks)
    raw_diff_pattern = r'^(diff --git.*?)(?=\n\n|\Z)'
    raw_match = re.search(raw_diff_pattern, text, re.MULTILINE | re.DOTALL)
    
    if raw_match:
        diff_content = raw_match.group(1).strip()
        return diff_content
    
    # Fallback: no diff found
    return ""


def extract_summary_from_response(text: str) -> str:
    """Extract problem-solving summary from XML tags."""
    
    # Look for SUMMARY XML tags (case insensitive, multiline)
    summary_pattern = r'<SUMMARY>(.*?)</SUMMARY>'
    summary_match = re.search(summary_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if summary_match:
        summary_content = summary_match.group(1).strip()
        return summary_content
    
    # No summary found
    return ""


def apply_patch(workdir: str, patch: str) -> bool:
    """Apply a patch to a working directory using git apply."""
    import subprocess
    import tempfile
    
    if not patch or not patch.strip():
        return False
        
    try:
        # Write patch to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
            f.write(patch)
            patch_file = f.name
        
        # Apply the patch
        result = subprocess.run(
            ['git', 'apply', patch_file],
            cwd=workdir,
            capture_output=True,
            text=True
        )
        
        # Clean up
        import os
        os.unlink(patch_file)
        
        if result.returncode == 0:
            return True
        else:
            logger.error(f"Failed to apply patch: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Exception applying patch: {e}")
        return False