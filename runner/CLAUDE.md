# SWE-Bench Solution Process

**CRITICAL INSTRUCTION**: When using The Force MCP tools for SWE-Bench tasks:
- Make intentional, deliberate choices about what to include in the context parameter
- You may include specific files, folders, or even the entire repository - but only after considering what's actually needed
- Do NOT automatically/blindly include the current working directory without thinking
- Consider: What context does the AI model need to understand and solve this specific problem?

When solving SWE-Bench problems, **ultrathink** through this exact 4-step process:

## Step 1: Analyze the Problem
First, carefully read and understand the problem statement. **Ultrathink** to identify:
- What the bug or issue is
- Where it's located in the codebase  
- What the expected behavior should be
- Use The Force MCP tools if you need to search code, analyze files, or get expert assistance

## Step 2: Develop the Solution
**Ultrathink** through the fix by leveraging all available tools:
- Use The Force tools (like chat_with_o3, chat_with_gemini25_pro) for complex analysis
- Execute code if needed to test your understanding
- Search through project files and codebase
- What needs to be changed and why this change will solve the problem
- Consider edge cases and compatibility

## Step 3: Summarize Your Process
Document your problem-solving approach in a summary section:

```
<SUMMARY>
Step-by-step summary of what I did to solve this problem:
1. [Describe analysis - what tools you used, what you discovered]
2. [Describe solution development - any code execution, file searches, consultations]
3. [Describe validation - how you verified the fix would work]
</SUMMARY>
```

## Step 4: Output Final Diff
Once you have determined the solution, output it as a git diff patch enclosed in XML tags:

```
<FINAL_DIFF>
diff --git a/path/to/file.py b/path/to/file.py
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,7 +10,7 @@ def function_name():
     # context line
-    old_line_to_change
+    new_line_with_fix
     # more context
</FINAL_DIFF>
```

## Format Examples

### Example 1: Simple function fix with summary
```
<SUMMARY>
Step-by-step summary of what I did to solve this problem:
1. Read the problem statement and identified that the add_numbers function was subtracting instead of adding
2. Used grep to search for other usages of this function in the codebase to understand the expected behavior
3. Consulted with chat_with_o3 to verify this was the correct approach and not a deeper design issue
4. Verified the fix by mentally tracing through test cases that would expect addition
</SUMMARY>

<FINAL_DIFF>
diff --git a/math_utils.py b/math_utils.py
--- a/math_utils.py
+++ b/math_utils.py
@@ -5,7 +5,7 @@ def add_numbers(a, b):
     Adds two numbers together.
     """
-    return a - b  # Bug: should be addition
+    return a + b  # Fixed: now correctly adds
</FINAL_DIFF>
```

### Example 2: Complex multi-file fix with tool usage
```
<SUMMARY>
Step-by-step summary of what I did to solve this problem:
1. Analyzed the error trace and identified the root cause was in the data validation pipeline
2. Used chat_with_gemini25_pro to get expert analysis on the data processing architecture
3. Searched through the codebase using glob patterns to find all related validation functions
4. Executed a simple test script to reproduce the issue and confirm my understanding
5. Used chat_with_o3 to review my proposed solution and ensure it handles edge cases
6. Verified the fix addresses both the immediate bug and prevents similar issues in the future
</SUMMARY>

<FINAL_DIFF>
diff --git a/data_processor.py b/data_processor.py
--- a/data_processor.py
+++ b/data_processor.py
@@ -15,10 +15,12 @@ def process_data(data):
     if not data:
         return []
     
-    # Old inefficient approach
-    result = []
-    for item in data:
-        result.append(transform(item))
+    # New efficient approach with validation
+    result = []
+    for item in data:
+        if validate_item(item):
+            result.append(transform(item))
+        else:
+            logger.warning(f"Invalid item skipped: {item}")
     
     return result
</FINAL_DIFF>
```

## Critical Requirements

1. **ALWAYS use the XML tags** `<FINAL_DIFF>` and `</FINAL_DIFF>`
2. **Start with `diff --git`** inside the tags
3. **Use proper unified diff format** with `---` and `+++` headers
4. **Include context lines** (lines starting with space, not + or -)
5. **NO markdown code blocks** inside the XML tags
6. **NO explanatory text** inside the XML tags - just the raw diff

The XML tags allow the parser to extract the diff even if you include explanatory text before or after them.