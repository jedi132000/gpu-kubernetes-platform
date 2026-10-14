"""Render check results as human- or machine-readable output."""

from __future__ import annotations

import json

from gpuctl.checks import ClusterState
from gpuctl.models import CheckResult, Status

_SYMBOLS = {
    Status.PASS: "PASS",
    Status.WARN: "WARN",
    Status.FAIL: "FAIL",
    Status.SKIP: "SKIP",
}

_STATE_MESSAGE = {
    ClusterState.UNREACHABLE: "Cluster unreachable - resolve connectivity before continuing.",
    ClusterState.NO_GPU_NODES: "CPU-only cluster - GPU workloads cannot be scheduled here.",
    ClusterState.MISSING_OPERATOR: "GPU nodes present but the GPU Operator is not installed.",
    ClusterState.UNHEALTHY_GPU: "GPU configuration is unhealthy - see failing checks below.",
    ClusterState.GPU_READY: "GPU environment verified and ready for accelerator workloads.",
}


def render_text(results: list[CheckResult], state: ClusterState) -> str:
    lines = ["GPU Kubernetes preflight", "=" * 24, ""]
    width = max((len(r.name) for r in results), default=0)
    for r in results:
        lines.append(f"[{_SYMBOLS[r.status]}] {r.name.ljust(width)}  {r.summary}")
        if r.remediation and r.status in (Status.FAIL, Status.WARN):
            lines.append(f"       -> {r.remediation}")
    lines.append("")
    lines.append(f"State: {state.value} - {_STATE_MESSAGE[state]}")
    return "\n".join(lines)


def render_json(results: list[CheckResult], state: ClusterState) -> str:
    payload = {
        "state": state.value,
        "state_message": _STATE_MESSAGE[state],
        "checks": [
            {
                "name": r.name,
                "status": r.status.value,
                "severity": r.severity.value,
                "summary": r.summary,
                "remediation": r.remediation,
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)
