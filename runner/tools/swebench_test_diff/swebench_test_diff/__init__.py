"""
fastmcp tool: run SWE-Bench tests for a diff on the remote tester service.

Environment
-----------
SWE_TESTER_URL : full http://host:port/test  (default http://swe-tester:8080/test)
"""

from fastmcp import tool, ValidationError
from pydantic import BaseModel, Field
import requests, os, time


TESTER_URL = os.environ.get("SWE_TESTER_URL", "http://35.209.45.223:8080/test")


class Input(BaseModel):
    instance_id: str = Field(...,  description="SWE-Bench instance ID, e.g. django__django-16595")
    patch:       str = Field(...,  description="Unified diff that should be applied")
    timeout:     int = Field(900, description="Seconds allowed for pytest")

class Output(BaseModel):
    passed:   int
    failed:   int
    errors:   int
    duration: float
    log_tail: str


@tool(
    name="swebench_test_diff",
    description="Compile & run pytest for a patch against SWE-Bench repos; "
                "returns pass/fail counts and log tail.",
    examples=[{
        "input": {
            "instance_id": "django__django-16595",
            "patch": "diff --git a/foo.py b/foo.py\n..."
        },
        "output": {
            "passed": 470, "failed": 0, "errors": 0,
            "duration": 130.7, "log_tail": "================= 470 passed in 128.55s ================="
        }
    }]
)
def swebench_test_diff(params: Input) -> Output:
    t0 = time.time()
    resp = requests.post(TESTER_URL, json=params.dict(), timeout=(5, params.timeout + 60))
    if resp.status_code != 200:
        raise ValidationError(f"tester returned {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    data.setdefault("duration", time.time() - t0)
    return Output(**data)