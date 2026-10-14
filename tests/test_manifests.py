"""Structural invariants for the Kubernetes manifests.

kubeconform validates the manifests against the Kubernetes OpenAPI schemas in
CI. These tests assert platform-specific rules the schema cannot express:
GPU workloads must request a GPU, tolerate the GPU taint, and pin to GPU nodes;
the CPU demo must do none of those.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SCHED = REPO / "kubernetes" / "scheduling"
CPU_DEMO = REPO / "kubernetes" / "cpu-demo"
GPU_RESOURCE = "nvidia.com/gpu"


def _load_all(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [doc for doc in yaml.safe_load_all(fh) if doc]


def _pod_spec(doc: dict) -> dict:
    kind = doc["kind"]
    if kind == "Pod":
        return doc["spec"]
    if kind in ("Deployment", "Job"):
        return doc["spec"]["template"]["spec"]
    raise AssertionError(f"unexpected kind {kind}")


def _requests_gpu(pod_spec: dict) -> bool:
    for c in pod_spec["containers"]:
        res = c.get("resources", {})
        for bucket in ("limits", "requests"):
            if GPU_RESOURCE in res.get(bucket, {}):
                return True
    return False


def _tolerates_gpu(pod_spec: dict) -> bool:
    return any(t.get("key") == GPU_RESOURCE for t in pod_spec.get("tolerations", []))


def test_all_manifests_parse():
    files = list(SCHED.glob("*.yaml")) + list(CPU_DEMO.glob("*.yaml"))
    assert files, "no manifests found"
    for f in files:
        docs = _load_all(f)
        assert docs, f"{f} produced no documents"
        for d in docs:
            assert "apiVersion" in d and "kind" in d, f"{f} missing apiVersion/kind"


def test_gpu_validation_job_requests_and_tolerates_gpu():
    doc = _load_all(SCHED / "02-gpu-validation-job.yaml")[0]
    spec = _pod_spec(doc)
    assert _requests_gpu(spec), "validation job must request a GPU"
    assert _tolerates_gpu(spec), "validation job must tolerate the GPU taint"
    # Must pin to GPU-present nodes via required node affinity.
    terms = spec["affinity"]["nodeAffinity"][
        "requiredDuringSchedulingIgnoredDuringExecution"
    ]["nodeSelectorTerms"]
    keys = {e["key"] for term in terms for e in term["matchExpressions"]}
    assert "nvidia.com/gpu.present" in keys


def test_cpu_demo_never_requests_or_tolerates_gpu():
    doc = _load_all(CPU_DEMO / "cpu-workload.yaml")[0]
    spec = _pod_spec(doc)
    assert not _requests_gpu(spec), "CPU demo must not request a GPU"
    assert not _tolerates_gpu(spec), "CPU demo must not tolerate the GPU taint"


def test_resource_quota_caps_gpu():
    docs = _load_all(SCHED / "00-namespace-quota.yaml")
    quota = next(d for d in docs if d["kind"] == "ResourceQuota")
    hard = quota["spec"]["hard"]
    assert "requests.nvidia.com/gpu" in hard
    assert "limits.nvidia.com/gpu" in hard


def test_priority_classes_not_global_default():
    docs = _load_all(SCHED / "01-priorityclasses.yaml")
    pcs = [d for d in docs if d["kind"] == "PriorityClass"]
    assert len(pcs) == 2
    # Never override cluster-wide default priority from this platform.
    assert all(pc.get("globalDefault", False) is False for pc in pcs)
    high = next(pc for pc in pcs if pc["metadata"]["name"] == "gpu-inference-high")
    low = next(pc for pc in pcs if pc["metadata"]["name"] == "gpu-batch-low")
    assert high["value"] > low["value"]


def test_pending_example_is_unsatisfiable():
    doc = _load_all(SCHED / "03-pending-pod-example.yaml")[0]
    spec = _pod_spec(doc)
    gpus = int(spec["containers"][0]["resources"]["limits"][GPU_RESOURCE])
    assert gpus >= 8, "example should request more GPUs than any single node provides"
