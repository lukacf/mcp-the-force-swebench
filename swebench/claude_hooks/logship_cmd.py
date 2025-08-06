#!/usr/bin/env python3
"""Streamlined logship command for Claude hooks via settings.json."""

import json
import sys
import os
import requests
import uuid
from datetime import datetime

def main():
    try:
        # Read hook event data from stdin
        event_data = sys.stdin.read().strip()
        if not event_data:
            sys.exit(0)
        
        event = json.loads(event_data)
        event_name = event.get("hook_event_name", "unknown")
        
        
        # Get environment variables
        run_id = os.getenv("RUN_ID", f"swe-{uuid.uuid4()}")
        instance_id = os.getenv("INSTANCE_ID", "unknown")
        vl_endpoint = os.getenv("VL_ENDPOINT", "http://localhost:9428/insert/elasticsearch/_bulk")
        
        # Create log record
        record = {
            "_time": "0",  # Let VictoriaLogs timestamp
            "run_id": run_id,
            "instance_id": instance_id,
            "hook_event": event_name,
            "state": _get_state(event_name, event),
            "tool": _get_tool(event),
            "app": "swe-bench-the-force",
            "_msg": f"[CLAUDE_HOOK] {_get_message(event_name, event)}"  # Clear tag prefix
        }
        
        # Add timing info for PostToolUse
        if event_name == "PostToolUse":
            record["duration_ms"] = int(event.get("duration_ms", 0))
        
        # Add full MCP command for MCP tool hooks
        tool_name = event.get("tool_name", "")
        if tool_name and tool_name.startswith("mcp__the-force__"):
            tool_input = event.get("tool_input", {})
            if tool_input:
                record["mcp_command"] = json.dumps(tool_input, separators=(',', ':'))
            
            # Add full MCP output for PostToolUse
            if event_name == "PostToolUse":
                tool_response = event.get("tool_response", [])
                if tool_response:
                    record["mcp_output"] = json.dumps(tool_response, separators=(',', ':'))
        
        # Ship to VictoriaLogs
        payload = '{ "create":{} }\n' + json.dumps(record) + '\n'
        requests.post(vl_endpoint, data=payload.encode(), timeout=1)
        
    except Exception:
        # Never break Claude - silently continue
        pass
    
    sys.exit(0)

def _get_state(event_name, event):
    if event_name == "SessionStart":
        return "session_start"
    elif event_name == "PreToolUse":
        return "tool_start"  
    elif event_name == "PostToolUse":
        return "tool_end"
    elif event_name == "Notification":
        return "heartbeat"
    elif event_name == "Stop":
        return "session_end"
    return "other"

def _get_tool(event):
    tool_name = event.get("tool_name", "unknown")
    if tool_name.startswith("mcp__the-force__"):
        return tool_name.replace("mcp__the-force__", "mcp:")
    return tool_name

def _get_message(event_name, event):
    if event_name == "SessionStart":
        return f"Started SWE-Bench session in {event.get('cwd', 'unknown directory')}"
    elif event_name == "PreToolUse":
        tool_name = event.get("tool_name", "")
        if tool_name == "Bash":
            cmd = event.get("tool_input", {}).get("command", "")
            return f"Executing: {cmd[:100]}"
        elif tool_name.startswith("mcp__the-force__"):
            mcp_tool = tool_name.replace("mcp__the-force__", "")
            return f"Calling MCP tool: {mcp_tool}"
        return f"Using tool: {tool_name}"
    elif event_name == "PostToolUse":
        tool_name = event.get("tool_name", "")
        if tool_name.startswith("mcp__the-force__"):
            mcp_tool = tool_name.replace("mcp__the-force__", "")
            return f"Completed MCP tool: {mcp_tool}"
        duration = event.get("duration_ms", 0)
        return f"Completed tool: {tool_name} in {duration}ms"
    elif event_name == "Notification":
        return event.get("message", "Claude heartbeat - still working")
    elif event_name == "Stop":
        return "SWE-Bench session completed"
    return f"Hook event: {event_name}"

if __name__ == "__main__":
    main()