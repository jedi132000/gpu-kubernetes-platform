"""Tests for the data models and snapshot (de)serialization round-trip."""

from __future__ import annotations

from gpuctl.models import ClusterSnapshot, NodeInfo


def test_allocatable_gpus_parsing():
    n = NodeInfo(name="g", allocatable={"nvidia.com/gpu": "4"})
    assert n.allocatable_gpus == 4


def test_allocatable_gpus_bad_value_is_zero():
    n = NodeInfo(name="g", allocatable={"nvidia.com/gpu": "not-a-number"})
    assert n.allocatable_gpus == 0


def test_is_gpu_node_via_label_before_plugin_ready():
    # Node labelled by NFD but device plugin has not advertised GPUs yet.
    n = NodeInfo(name="g", labels={"nvidia.com/gpu.present": "true"}, allocatable={})
    assert n.is_gpu_node is True
    assert n.allocatable_gpus == 0


def test_is_gpu_node_via_allocatable():
    n = NodeInfo(name="g", allocatable={"nvidia.com/gpu": "1"})
    assert n.is_gpu_node is True


def test_cpu_node_is_not_gpu_node():
    n = NodeInfo(name="c", allocatable={"cpu": "8"})
    assert n.is_gpu_node is False


def test_has_gpu_taint():
    n = NodeInfo(name="g", taints=[{"key": "nvidia.com/gpu", "effect": "NoSchedule"}])
    assert n.has_gpu_taint is True


def test_snapshot_json_round_trip():
    snap = ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[NodeInfo(name="g", labels={"a": "b"}, allocatable={"nvidia.com/gpu": "2"})],
    )
    restored = ClusterSnapshot.from_dict(snap.to_dict())
    assert restored.reachable is True
    assert restored.server_version == "v1.31.4"
    assert restored.total_allocatable_gpus == 2
    assert restored.nodes[0].labels == {"a": "b"}
