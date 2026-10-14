"""Tests for the pure preflight checks and state classification."""

from __future__ import annotations

from gpuctl.checks import (
    ClusterState,
    classify,
    exit_code,
    run_all_checks,
)
from gpuctl.models import Status


def _by_name(results):
    return {r.name: r for r in results}


def test_unreachable_classifies_and_blocks(unreachable):
    results = run_all_checks(unreachable)
    assert classify(unreachable, results) is ClusterState.UNREACHABLE
    assert _by_name(results)["api-connectivity"].status is Status.FAIL
    # Downstream checks are skipped, not failed.
    assert _by_name(results)["gpu-nodes"].status is Status.SKIP
    assert exit_code(results) == 1


def test_cpu_only_is_warn_not_fail(cpu_only):
    results = run_all_checks(cpu_only)
    assert classify(cpu_only, results) is ClusterState.NO_GPU_NODES
    names = _by_name(results)
    assert names["api-connectivity"].status is Status.PASS
    assert names["gpu-nodes"].status is Status.WARN
    # GPU-specific checks skip cleanly on a CPU-only cluster.
    assert names["allocatable-gpus"].status is Status.SKIP
    assert names["gpu-operator"].status is Status.SKIP
    assert exit_code(results) == 2  # warnings only, no critical failure


def test_missing_operator(missing_operator):
    results = run_all_checks(missing_operator)
    assert classify(missing_operator, results) is ClusterState.MISSING_OPERATOR
    names = _by_name(results)
    assert names["gpu-operator"].status is Status.FAIL
    assert "No GPU Operator pods" in names["gpu-operator"].summary
    assert exit_code(results) == 1


def test_unhealthy_gpu_zero_allocatable(unhealthy_gpu):
    results = run_all_checks(unhealthy_gpu)
    assert classify(unhealthy_gpu, results) is ClusterState.UNHEALTHY_GPU
    names = _by_name(results)
    assert names["allocatable-gpus"].status is Status.FAIL
    assert names["device-plugin"].status is Status.FAIL
    assert exit_code(results) == 1


def test_gpu_ready(gpu_ready):
    results = run_all_checks(gpu_ready)
    assert classify(gpu_ready, results) is ClusterState.GPU_READY
    names = _by_name(results)
    assert names["allocatable-gpus"].status is Status.PASS
    assert names["gpu-operator"].status is Status.PASS
    assert names["device-plugin"].status is Status.PASS
    assert names["gpu-taints"].status is Status.PASS
    assert exit_code(results) == 0


def test_untainted_gpu_node_warns(gpu_ready):
    # Remove the taint from the ready cluster and confirm only a warning.
    from dataclasses import replace

    node = replace(gpu_ready.nodes[0], taints=[])
    snap = replace(gpu_ready, nodes=[node])
    results = run_all_checks(snap)
    names = _by_name(results)
    assert names["gpu-taints"].status is Status.WARN
    # Still GPU-ready: taint is an advisory warning, not a blocker.
    assert classify(snap, results) is ClusterState.GPU_READY
    assert exit_code(results) == 2


def test_pending_gpu_pod_detected(gpu_ready):
    from dataclasses import replace

    from gpuctl.models import PodInfo

    pending = PodInfo(
        name="trainer-0",
        namespace="ml",
        phase="Pending",
        reason="0/1 nodes are available: 1 Insufficient nvidia.com/gpu.",
    )
    snap = replace(gpu_ready, pods=[*gpu_ready.pods, pending])
    results = run_all_checks(snap)
    assert _by_name(results)["pending-gpu-pods"].status is Status.WARN


def test_old_k8s_version_warns(gpu_ready):
    from dataclasses import replace

    snap = replace(gpu_ready, server_version="v1.24.0")
    results = run_all_checks(snap)
    assert _by_name(results)["k8s-version"].status is Status.WARN
