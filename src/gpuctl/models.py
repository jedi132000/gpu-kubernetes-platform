"""Data models shared across the preflight checks.

These are intentionally plain dataclasses rather than Kubernetes client
objects. ``gpuctl.kube`` converts live API responses into these structures,
which keeps the check logic in ``gpuctl.checks`` pure and unit-testable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

# Canonical resource name advertised by the NVIDIA device plugin.
GPU_RESOURCE = "nvidia.com/gpu"

# Label applied by the GPU Operator's node-feature-discovery to nodes that
# carry an NVIDIA GPU. Used to detect GPU nodes independently of allocatable
# resources (a node can be a GPU node while the device plugin is not yet ready).
NFD_GPU_LABEL = "nvidia.com/gpu.present"

# The taint this platform expects on dedicated GPU nodes. See
# kubernetes/scheduling and docs/adr/0001 for the rationale.
GPU_TAINT_KEY = "nvidia.com/gpu"


class Status(str, Enum):
    """Outcome of a single check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class Severity(str, Enum):
    """How much a failing check should influence the overall exit code."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NodeInfo:
    """A condensed view of a Kubernetes node relevant to GPU scheduling."""

    name: str
    labels: dict[str, str] = field(default_factory=dict)
    taints: list[dict[str, str]] = field(default_factory=list)
    allocatable: dict[str, str] = field(default_factory=dict)
    ready: bool = True

    @property
    def allocatable_gpus(self) -> int:
        raw = self.allocatable.get(GPU_RESOURCE, "0")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @property
    def is_gpu_node(self) -> bool:
        """True if the node is labelled as a GPU node or advertises GPUs.

        We check the NFD label first because allocatable GPUs only appear once
        the device plugin is healthy; a freshly provisioned GPU node should
        still be recognised as a GPU node so missing-device-plugin conditions
        are reported accurately rather than as "no GPU nodes".
        """

        if self.labels.get(NFD_GPU_LABEL) == "true":
            return True
        return self.allocatable_gpus > 0

    @property
    def has_gpu_taint(self) -> bool:
        return any(t.get("key") == GPU_TAINT_KEY for t in self.taints)


@dataclass(frozen=True)
class PodInfo:
    """A condensed view of a pod, used for operator/device-plugin health."""

    name: str
    namespace: str
    phase: str
    labels: dict[str, str] = field(default_factory=dict)
    node_name: str | None = None
    ready: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class ClusterSnapshot:
    """Everything the checks need, collected in one pass from the API.

    ``reachable`` is False when the API server could not be contacted; in that
    case the remaining fields are empty and connectivity-dependent checks are
    reported as failures rather than silently passing.
    """

    reachable: bool
    server_version: str | None = None
    nodes: list[NodeInfo] = field(default_factory=list)
    pods: list[PodInfo] = field(default_factory=list)
    error: str | None = None

    @property
    def gpu_nodes(self) -> list[NodeInfo]:
        return [n for n in self.nodes if n.is_gpu_node]

    @property
    def total_allocatable_gpus(self) -> int:
        return sum(n.allocatable_gpus for n in self.gpu_nodes)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterSnapshot:
        """Rebuild a snapshot from the JSON produced by :meth:`to_dict`."""

        return cls(
            reachable=bool(data.get("reachable", False)),
            server_version=data.get("server_version"),
            error=data.get("error"),
            nodes=[
                NodeInfo(
                    name=n["name"],
                    labels=n.get("labels", {}),
                    taints=n.get("taints", []),
                    allocatable=n.get("allocatable", {}),
                    ready=n.get("ready", True),
                )
                for n in data.get("nodes", [])
            ],
            pods=[
                PodInfo(
                    name=p["name"],
                    namespace=p["namespace"],
                    phase=p.get("phase", "Unknown"),
                    labels=p.get("labels", {}),
                    node_name=p.get("node_name"),
                    ready=p.get("ready", False),
                    reason=p.get("reason"),
                )
                for p in data.get("pods", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class CheckResult:
    """The result of a single named check."""

    name: str
    status: Status
    severity: Severity
    summary: str
    remediation: str | None = None

    @property
    def is_blocking(self) -> bool:
        """A failed critical check should fail the whole preflight run."""

        return self.status == Status.FAIL and self.severity == Severity.CRITICAL
