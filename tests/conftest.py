"""Shared fixtures: synthetic cluster snapshots for each supported state."""

from __future__ import annotations

import pytest

from gpuctl.models import ClusterSnapshot, NodeInfo, PodInfo

GPU_ALLOC = {"cpu": "4", "memory": "16Gi", "nvidia.com/gpu": "1"}
GPU_TAINT = [{"key": "nvidia.com/gpu", "value": "present", "effect": "NoSchedule"}]


def _operator_pods(ready: bool = True, with_plugin: bool = True) -> list[PodInfo]:
    pods = [
        PodInfo(
            "gpu-operator-abc", "gpu-operator", "Running", {"app": "gpu-operator"}, ready=ready
        ),
        PodInfo("nvidia-driver-daemonset-x", "gpu-operator", "Running", {}, ready=ready),
        PodInfo("nvidia-dcgm-exporter-y", "gpu-operator", "Running", {}, ready=ready),
    ]
    if with_plugin:
        pods.append(
            PodInfo("nvidia-device-plugin-daemonset-z", "gpu-operator", "Running", {}, ready=ready)
        )
    return pods


@pytest.fixture
def unreachable() -> ClusterSnapshot:
    return ClusterSnapshot(reachable=False, error="connection refused")


@pytest.fixture
def cpu_only() -> ClusterSnapshot:
    return ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[NodeInfo(name="cpu-1", allocatable={"cpu": "4", "memory": "16Gi"})],
        pods=[],
    )


@pytest.fixture
def missing_operator() -> ClusterSnapshot:
    return ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[
            NodeInfo(
                name="gpu-1",
                labels={"nvidia.com/gpu.present": "true"},
                taints=GPU_TAINT,
                allocatable={"cpu": "4", "memory": "16Gi"},  # no GPUs yet
            )
        ],
        pods=[],
    )


@pytest.fixture
def unhealthy_gpu() -> ClusterSnapshot:
    # GPU node labelled present, operator running, but device plugin advertises
    # zero allocatable GPUs (driver/plugin not healthy).
    return ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[
            NodeInfo(
                name="gpu-1",
                labels={"nvidia.com/gpu.present": "true"},
                taints=GPU_TAINT,
                allocatable={"cpu": "4", "memory": "16Gi", "nvidia.com/gpu": "0"},
            )
        ],
        pods=_operator_pods(ready=True, with_plugin=False),
    )


@pytest.fixture
def gpu_ready() -> ClusterSnapshot:
    return ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[
            NodeInfo(
                name="gpu-1",
                labels={"nvidia.com/gpu.present": "true"},
                taints=GPU_TAINT,
                allocatable=GPU_ALLOC,
            )
        ],
        pods=_operator_pods(ready=True, with_plugin=True),
    )
