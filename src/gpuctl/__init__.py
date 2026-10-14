"""gpuctl: preflight and validation tooling for GPU-aware Kubernetes clusters.

The package is split into three layers so that the diagnostic logic can be
tested without a live cluster:

* :mod:`gpuctl.models`  - plain data structures describing a cluster snapshot.
* :mod:`gpuctl.checks`  - pure functions that turn a snapshot into findings.
* :mod:`gpuctl.kube`    - the only layer that talks to the Kubernetes API.

:mod:`gpuctl.cli` wires them together.
"""

from gpuctl.models import (
    CheckResult,
    ClusterSnapshot,
    NodeInfo,
    PodInfo,
    Severity,
    Status,
)

__all__ = [
    "CheckResult",
    "ClusterSnapshot",
    "NodeInfo",
    "PodInfo",
    "Severity",
    "Status",
    "__version__",
]

__version__ = "0.1.0"
