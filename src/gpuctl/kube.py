"""Collect a :class:`~gpuctl.models.ClusterSnapshot` from a live cluster.

This is the only module that imports the Kubernetes client. The import is
deferred so the rest of the package (and its tests) work without the optional
``kubernetes`` dependency installed. All API calls use a bounded request
timeout so a hung API server fails fast rather than blocking the CLI.
"""

from __future__ import annotations

from typing import Any

from gpuctl.models import ClusterSnapshot, NodeInfo, PodInfo

# Seconds; applied to each list call so a stuck API server fails fast.
DEFAULT_TIMEOUT = 15


class ClusterAccessError(RuntimeError):
    """Raised when the cluster cannot be reached or queried."""


def _load_clients(kubeconfig: str | None, context: str | None) -> Any:
    try:
        import kubernetes.client as client
        import kubernetes.config as config
    except ImportError as exc:  # pragma: no cover - exercised via CLI message
        raise ClusterAccessError(
            "The 'kubernetes' package is required for live checks. "
            "Install it with: pip install 'gpuctl[cluster]'"
        ) from exc

    try:
        # In-cluster config takes precedence when running inside a pod.
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config(config_file=kubeconfig, context=context)
    except Exception as exc:  # noqa: BLE001 - surface any config failure uniformly
        raise ClusterAccessError(f"Failed to load Kubernetes configuration: {exc}") from exc

    return client.CoreV1Api(), client.VersionApi()


def _node_ready(node: Any) -> bool:
    for cond in node.status.conditions or []:
        if cond.type == "Ready":
            return bool(cond.status == "True")
    return False


def _pod_ready(pod: Any) -> bool:
    statuses = pod.status.container_statuses or []
    return bool(statuses) and all(cs.ready for cs in statuses)


def _pod_reason(pod: Any) -> str | None:
    """Best-effort scheduling/termination reason for diagnostics."""

    for cond in pod.status.conditions or []:
        if cond.type == "PodScheduled" and cond.status == "False" and cond.message:
            return str(cond.message)
    reason = pod.status.reason
    return str(reason) if reason is not None else None


def collect_snapshot(
    kubeconfig: str | None = None,
    context: str | None = None,
    operator_namespace: str = "gpu-operator",
    timeout: int = DEFAULT_TIMEOUT,
) -> ClusterSnapshot:
    """Query the cluster and return a populated ClusterSnapshot.

    On any connectivity/authorization failure a snapshot with
    ``reachable=False`` and a populated ``error`` is returned instead of
    raising, so the checks can report it uniformly.
    """

    try:
        core, version_api = _load_clients(kubeconfig, context)
    except ClusterAccessError as exc:
        return ClusterSnapshot(reachable=False, error=str(exc))

    try:
        version = version_api.get_code()
        server_version = f"v{version.major}.{version.minor}".rstrip("+")
    except Exception as exc:  # noqa: BLE001
        return ClusterSnapshot(reachable=False, error=f"version query failed: {exc}")

    try:
        node_list = core.list_node(timeout_seconds=timeout, _request_timeout=timeout)
        nodes = [
            NodeInfo(
                name=n.metadata.name,
                labels=n.metadata.labels or {},
                taints=[
                    {"key": t.key, "value": t.value or "", "effect": t.effect or ""}
                    for t in (n.spec.taints or [])
                ],
                allocatable=dict(n.status.allocatable or {}),
                ready=_node_ready(n),
            )
            for n in node_list.items
        ]
    except Exception as exc:  # noqa: BLE001
        return ClusterSnapshot(
            reachable=True,
            server_version=server_version,
            error=f"node query failed: {exc}",
        )

    # Pods are only needed from the operator namespace plus any Pending pods
    # cluster-wide (for the pending-GPU diagnostic). We read the operator
    # namespace explicitly and rely on field selectors for pending pods.
    pods: list[PodInfo] = []
    try:
        ns_pods = core.list_namespaced_pod(
            namespace=operator_namespace,
            timeout_seconds=timeout,
            _request_timeout=timeout,
        )
        pods.extend(_to_pod_infos(ns_pods.items))
    except Exception:  # noqa: BLE001 - namespace may not exist yet; not fatal
        pass

    try:
        pending = core.list_pod_for_all_namespaces(
            field_selector="status.phase=Pending",
            timeout_seconds=timeout,
            _request_timeout=timeout,
        )
        seen = {(p.namespace, p.name) for p in pods}
        pods.extend(p for p in _to_pod_infos(pending.items) if (p.namespace, p.name) not in seen)
    except Exception:  # noqa: BLE001
        pass

    return ClusterSnapshot(
        reachable=True,
        server_version=server_version,
        nodes=nodes,
        pods=pods,
    )


def _to_pod_infos(items: list[Any]) -> list[PodInfo]:
    result = []
    for p in items:
        result.append(
            PodInfo(
                name=p.metadata.name,
                namespace=p.metadata.namespace,
                phase=p.status.phase or "Unknown",
                labels=p.metadata.labels or {},
                node_name=p.spec.node_name,
                ready=_pod_ready(p),
                reason=_pod_reason(p),
            )
        )
    return result
