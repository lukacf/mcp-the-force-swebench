#!/usr/bin/env python3
"""Ship Claude hook events to VictoriaLogs for real-time SWE-Bench monitoring."""

import json
import os
import sys
import datetime
import requests
import uuid
import traceback
from typing import Dict, Any

# Configuration from environment
VL_ENDPOINT = os.getenv("VL_ENDPOINT", "http://localhost:9428/insert/elasticsearch/_bulk")
RUN_ID = os.getenv("RUN_ID", f"swebench-{uuid.uuid4()}")
INSTANCE_ID = os.getenv("INSTANCE_ID", "unknown")
DEBUG_HOOKS = os.getenv("DEBUG_HOOKS", "false").lower() == "true"

def debug_log(msg: str):
    """Debug logging that doesn't interfere with Claude."""
    if DEBUG_HOOKS:
        with open("/tmp/claude_hooks_debug.log", "a") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {msg}\n")

def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Claude hook event to structured log record."""
    
    base_record = {
        "_time": "0",  # Let VictoriaLogs auto-timestamp
        "run_id": RUN_ID,
        "instance_id": INSTANCE_ID,
        "hook_event": event["hookEventName"],
    }
    
    event_name = event["hookEventName"]
    
    if event_name == "SessionStart":
        return {
            **base_record,
            "state": "session_start",
            "tool": "session",
            "msg": f"Starting SWE-Bench evaluation for {INSTANCE_ID}"
        }
    
    elif event_name == "PreToolUse":
        tool_name = event.get("tool_name", "unknown")
        tool_input = event.get("tool_input", {})
        
        # Extract meaningful info based on tool type
        if tool_name == "Bash":
            msg = f"Executing: {tool_input.get('command', 'unknown command')}"
        elif tool_name in ["Edit", "Write", "Read"]:
            file_path = tool_input.get('file_path', 'unknown file')
            msg = f"{tool_name}: {file_path}"
        elif tool_name.startswith("mcp__the-force__"):
            mcp_tool = tool_name.replace("mcp__the-force__", "")
            msg = f"MCP Tool: {mcp_tool}"
        else:
            msg = f"Tool: {tool_name} with input: {str(tool_input)[:100]}"
        
        return {
            **base_record,
            "state": "tool_start",
            "tool": tool_name,
            "task_id": event.get("tool_call_id", "unknown"),
            "msg": msg
        }
    
    elif event_name == "PostToolUse":
        tool_name = event.get("tool_name", "unknown")
        duration_ms = int(event.get("duration_ms", 0))
        
        # Determine success/failure
        result = event.get("result", {})
        error = event.get("error")
        success = not error and result
        
        msg_parts = []
        if error:
            msg_parts.append(f"ERROR: {str(error)[:100]}")
        elif result:
            # Show brief result preview
            if isinstance(result, str):
                msg_parts.append(f"Result: {result[:100]}")
            else:
                msg_parts.append("Completed successfully")
        
        msg_parts.append(f"Duration: {duration_ms}ms")
        
        return {
            **base_record,
            "state": "tool_end",
            "tool": tool_name,
            "task_id": event.get("tool_call_id", "unknown"),
            "duration_ms": duration_ms,
            "success": success,
            "msg": " | ".join(msg_parts)
        }
    
    elif event_name == "Notification":
        return {
            **base_record,
            "state": "heartbeat",
            "tool": "system",
            "msg": event.get("message", "Claude heartbeat - still working")
        }
    
    elif event_name == "Stop":
        return {
            **base_record,
            "state": "session_end",
            "tool": "session",
            "msg": f"SWE-Bench evaluation completed for {INSTANCE_ID}"
        }
    
    else:
        return {
            **base_record,
            "state": "other",
            "tool": "unknown",
            "msg": f"Unknown event: {event_name}"
        }

def ship_to_victoria_logs(record: Dict[str, Any]):
    """Send log record to VictoriaLogs via Elasticsearch bulk API."""
    try:
        # Elasticsearch bulk format: { "create":{} }\n{ actual_record }\n
        payload = '{ "create":{} }\n' + json.dumps(record) + '\n'
        
        debug_log(f"Shipping to VL: {record}")
        
        response = requests.post(
            VL_ENDPOINT,
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/x-ndjson'},
            timeout=2  # Don't block Claude for too long
        )
        
        if response.status_code not in [200, 201, 204]:
            debug_log(f"VL error: {response.status_code} {response.text}")
            
    except Exception as e:
        # Never break Claude - log error but continue
        debug_log(f"Ship error: {e}")

def main():
    """Main hook entry point."""
    try:
        # Read event from stdin
        event_data = sys.stdin.read()
        if not event_data.strip():
            debug_log("No event data received")
            return
        
        event = json.loads(event_data)
        debug_log(f"Received event: {event.get('hookEventName', 'unknown')}")
        
        # Normalize and ship
        record = normalize_event(event)
        ship_to_victoria_logs(record)
        
        # Exit successfully so Claude continues
        sys.exit(0)
        
    except Exception as e:
        # Log error but don't fail Claude
        debug_log(f"Hook error: {e}\n{traceback.format_exc()}")
        sys.exit(0)  # Always succeed from Claude's perspective

if __name__ == "__main__":
    main()