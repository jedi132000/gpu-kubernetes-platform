"""Pure preflight checks over a :class:`~gpuctl.models.ClusterSnapshot`.

Every function here takes a snapshot (and optional configuration) and returns
:class:`~gpuctl.models.CheckResult` objects. No function performs I/O, which is
what lets the full matrix of cluster states be exercised in unit tests.
"""

from __future__ import annotations

import re
from enum import Enum

from gpuctl.models import (
    CheckResult,
    ClusterSnapshot,
    Severity,
    Status,
)

# Minimum Kubernetes control-plane version this platform is validated against.
# Keep in sync with terraform/variables.tf (cluster_version) and the README
# compatibility table.
MIN_K8S_MINOR = (1, 28)

# Default namespace the NVIDIA GPU Operator Helm chart installs into.
DEFAULT_OPERATOR_NAMESPACE = "gpu-operator"

# Substrings identifying operator-managed workloads by their app labels /
# pod-name prefixes. The device plugin is tracked separately below.
_OPERATOR_COMPONENTS = (
    "gpu-operator",
    "nvidia-driver-daemonset",
    "nvidia-container-toolkit",
    "nvidia-dcgm-exporter",
)
_DEVICE_PLUGIN_MARKER = "nvidia-device-plugin"


class ClusterState(str, Enum):
    """High-level classification derived from the individual checks."""

    UNREACHABLE = "unreachable"
    NO_GPU_NODES = "no_gpu_nodes"
    MISSING_OPERATOR = "missing_operator"
    UNHEALTHY_GPU = "unhealthy_gpu"
    GPU_READY = "gpu_ready"


def _parse_minor(version: str | None) -> tuple[int, int] | None:
    """Extract ``(major, minor)`` from a Kubernetes version string.

    Accepts forms like ``v1.31.4``, ``1.31``, or EKS' ``v1.31.4-eks-abc1234``.
    """

    if not version:
        return None
    match = re.search(r"v?(\d+)\.(\d+)", version)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def check_connectivity(snapshot: ClusterSnapshot) -> CheckResult:
    if snapshot.reachable:
        return CheckResult(
            name="api-connectivity",
            status=Status.PASS,
            severity=Severity.CRITICAL,
            summary="Reached the Kubernetes API server.",
        )
    detail = snapshot.error or "unknown error"
    return CheckResult(
        name="api-connectivity",
        status=Status.FAIL,
        severity=Severity.CRITICAL,
        summary=f"Could not reach the Kubernetes API server: {detail}",
        remediation="Check your kubeconfig context, credentials, and network reachability.",
    )


def check_server_version(snapshot: ClusterSnapshot) -> CheckResult:
    if not snapshot.reachable:
        return CheckResult(
            name="k8s-version",
            status=Status.SKIP,
            severity=Severity.INFO,
            summary="Skipped: cluster unreachable.",
        )
    parsed = _parse_minor(snapshot.server_version)
    if parsed is None:
        return CheckResult(
            name="k8s-version",
            status=Status.WARN,
            severity=Severity.WARNING,
            summary=f"Could not parse server version {snapshot.server_version!r}.",
        )
    if parsed < MIN_K8S_MINOR:
        want = ".".join(map(str, MIN_K8S_MINOR))
        have = ".".join(map(str, parsed))
        return CheckResult(
            name="k8s-version",
            status=Status.WARN,
            severity=Severity.WARNING,
            summary=f"Cluster is {have}; this platform targets >= {want}.",
            remediation="Upgrade the control plane or pin a GPU Operator release that supports it.",
        )
    return CheckResult(
        name="k8s-version",
        status=Status.PASS,
        severity=Severity.INFO,
        summary=f"Control plane version {snapshot.server_version} is supported.",
    )


def check_gpu_nodes(snapshot: ClusterSnapshot) -> CheckResult:
    if not snapshot.reachable:
        return _skip("gpu-nodes")
    gpu_nodes = snapshot.gpu_nodes
    if not gpu_nodes:
        # Not a failure: a CPU-only cluster is a valid, supported target for
        # the CPU demo workloads. We surface it as a warning so operators who
        # *expected* GPUs notice, without failing the run.
        return CheckResult(
            name="gpu-nodes",
            status=Status.WARN,
            severity=Severity.WARNING,
            summary="No GPU nodes detected (CPU-only cluster).",
            remediation="Add a GPU node group, or run the CPU-only demo under kubernetes/cpu-demo.",
        )
    return CheckResult(
        name="gpu-nodes",
        status=Status.PASS,
        severity=Severity.INFO,
        summary=f"Found {len(gpu_nodes)} GPU node(s): {', '.join(n.name for n in gpu_nodes)}.",
    )


def check_allocatable_gpus(snapshot: ClusterSnapshot) -> CheckResult:
    if not snapshot.reachable:
        return _skip("allocatable-gpus")
    gpu_nodes = snapshot.gpu_nodes
    if not gpu_nodes:
        return _skip("allocatable-gpus", "No GPU nodes to inspect.")
    total = snapshot.total_allocatable_gpus
    if total == 0:
        # GPU nodes exist but advertise zero allocatable GPUs: the device
        # plugin is not registering capacity. This is the classic
        # "unhealthy GPU" state and must block.
        return CheckResult(
            name="allocatable-gpus",
            status=Status.FAIL,
            severity=Severity.CRITICAL,
            summary="GPU nodes present but 0 allocatable nvidia.com/gpu resources.",
            remediation=(
                "Check the NVIDIA device plugin and driver pods in the gpu-operator namespace."
            ),
        )
    return CheckResult(
        name="allocatable-gpus",
        status=Status.PASS,
        severity=Severity.INFO,
        summary=f"{total} allocatable nvidia.com/gpu across {len(gpu_nodes)} node(s).",
    )


def check_gpu_taints(snapshot: ClusterSnapshot) -> CheckResult:
    if not snapshot.reachable:
        return _skip("gpu-taints")
    gpu_nodes = snapshot.gpu_nodes
    if not gpu_nodes:
        return _skip("gpu-taints", "No GPU nodes to inspect.")
    untainted = [n.name for n in gpu_nodes if not n.has_gpu_taint]
    if untainted:
        return CheckResult(
            name="gpu-taints",
            status=Status.WARN,
            severity=Severity.WARNING,
            summary=f"GPU node(s) without the dedicated taint: {', '.join(untainted)}.",
            remediation=(
                "Apply the nvidia.com/gpu taint so ordinary pods do not consume "
                "accelerator nodes (see kubernetes/scheduling)."
            ),
        )
    return CheckResult(
        name="gpu-taints",
        status=Status.PASS,
        severity=Severity.INFO,
        summary="All GPU nodes carry the dedicated nvidia.com/gpu taint.",
    )


def _matches_operator(pod_identity: str) -> bool:
    return any(component in pod_identity for component in _OPERATOR_COMPONENTS)


def check_gpu_operator(
    snapshot: ClusterSnapshot,
    namespace: str = DEFAULT_OPERATOR_NAMESPACE,
) -> CheckResult:
    if not snapshot.reachable:
        return _skip("gpu-operator")
    gpu_nodes = snapshot.gpu_nodes
    operator_pods = [
        p
        for p in snapshot.pods
        if p.namespace == namespace and _matches_operator(f"{p.name} {p.labels.get('app', '')}")
    ]
    if not operator_pods:
        if not gpu_nodes:
            return _skip("gpu-operator", "No GPU nodes; operator not required.")
        return CheckResult(
            name="gpu-operator",
            status=Status.FAIL,
            severity=Severity.CRITICAL,
            summary=f"No GPU Operator pods found in namespace '{namespace}'.",
            remediation="Install the NVIDIA GPU Operator Helm chart (see helm/gpu-operator).",
        )
    not_ready = [p.name for p in operator_pods if not p.ready]
    if not_ready:
        return CheckResult(
            name="gpu-operator",
            status=Status.FAIL,
            severity=Severity.CRITICAL,
            summary=f"GPU Operator component(s) not ready: {', '.join(not_ready)}.",
            remediation="Inspect pod logs and events in the gpu-operator namespace.",
        )
    return CheckResult(
        name="gpu-operator",
        status=Status.PASS,
        severity=Severity.INFO,
        summary=f"{len(operator_pods)} GPU Operator component pod(s) ready in '{namespace}'.",
    )


def check_device_plugin(
    snapshot: ClusterSnapshot,
    namespace: str = DEFAULT_OPERATOR_NAMESPACE,
) -> CheckResult:
    if not snapshot.reachable:
        return _skip("device-plugin")
    gpu_nodes = snapshot.gpu_nodes
    if not gpu_nodes:
        return _skip("device-plugin", "No GPU nodes; device plugin not required.")
    plugin_pods = [
        p for p in snapshot.pods if p.namespace == namespace and _DEVICE_PLUGIN_MARKER in p.name
    ]
    if not plugin_pods:
        return CheckResult(
            name="device-plugin",
            status=Status.FAIL,
            severity=Severity.CRITICAL,
            summary="NVIDIA device plugin pods not found.",
            remediation=(
                "The GPU Operator manages the device plugin; verify its DaemonSet rolled out."
            ),
        )
    not_ready = [p.name for p in plugin_pods if not p.ready]
    if not_ready:
        return CheckResult(
            name="device-plugin",
            status=Status.FAIL,
            severity=Severity.CRITICAL,
            summary=f"Device plugin pod(s) not ready: {', '.join(not_ready)}.",
            remediation="Check node driver readiness; the plugin waits for the NVIDIA driver.",
        )
    return CheckResult(
        name="device-plugin",
        status=Status.PASS,
        severity=Severity.INFO,
        summary=f"{len(plugin_pods)} device plugin pod(s) ready.",
    )


def check_pending_gpu_pods(snapshot: ClusterSnapshot) -> CheckResult:
    """Report pods stuck Pending with a GPU-related scheduling reason."""

    if not snapshot.reachable:
        return _skip("pending-gpu-pods")
    pending = [
        p
        for p in snapshot.pods
        if p.phase == "Pending"
        and p.reason
        and ("Insufficient nvidia.com/gpu" in p.reason or "nvidia.com/gpu" in p.reason)
    ]
    if pending:
        names = ", ".join(f"{p.namespace}/{p.name}" for p in pending)
        return CheckResult(
            name="pending-gpu-pods",
            status=Status.WARN,
            severity=Severity.WARNING,
            summary=f"{len(pending)} pod(s) pending on GPU capacity: {names}.",
            remediation=(
                "Scale the GPU node group or reduce requested GPUs; see docs/troubleshooting.md."
            ),
        )
    return CheckResult(
        name="pending-gpu-pods",
        status=Status.PASS,
        severity=Severity.INFO,
        summary="No pods pending on GPU capacity.",
    )


def _skip(name: str, reason: str = "Skipped: cluster unreachable.") -> CheckResult:
    return CheckResult(name=name, status=Status.SKIP, severity=Severity.INFO, summary=reason)


# Order matters: connectivity first, then capability, then workload health.
ALL_CHECKS = (
    check_connectivity,
    check_server_version,
    check_gpu_nodes,
    check_allocatable_gpus,
    check_gpu_taints,
    check_gpu_operator,
    check_device_plugin,
    check_pending_gpu_pods,
)


def run_all_checks(
    snapshot: ClusterSnapshot,
    operator_namespace: str = DEFAULT_OPERATOR_NAMESPACE,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in ALL_CHECKS:
        if check in (check_gpu_operator, check_device_plugin):
            results.append(check(snapshot, operator_namespace))
        else:
            results.append(check(snapshot))
    return results


def classify(snapshot: ClusterSnapshot, results: list[CheckResult]) -> ClusterState:
    """Map check results to one of the five documented cluster states."""

    by_name = {r.name: r for r in results}
    if not snapshot.reachable:
        return ClusterState.UNREACHABLE
    if not snapshot.gpu_nodes:
        return ClusterState.NO_GPU_NODES
    if by_name["gpu-operator"].status == Status.FAIL and "No GPU Operator pods" in (
        by_name["gpu-operator"].summary
    ):
        return ClusterState.MISSING_OPERATOR
    blocking = [r for r in results if r.is_blocking]
    if blocking:
        return ClusterState.UNHEALTHY_GPU
    return ClusterState.GPU_READY


def exit_code(results: list[CheckResult]) -> int:
    """0 = all good, 1 = a critical check failed, 2 = warnings only."""

    if any(r.is_blocking for r in results):
        return 1
    if any(r.status == Status.WARN for r in results):
        return 2
    return 0
