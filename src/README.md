# gpuctl

Preflight and validation CLI for GPU-aware Kubernetes clusters. Part of the
[gpu-kubernetes-platform](../README.md) repository.

`gpuctl` collects a read-only snapshot of a cluster (nodes, allocatable GPU
resources, taints/labels, GPU Operator and device-plugin pod health, pending
GPU pods) and reports whether the cluster is one of:

- unreachable
- CPU-only (no GPU nodes)
- GPU nodes present but the GPU Operator is missing
- GPU configuration unhealthy (e.g. device plugin advertising 0 GPUs)
- GPU-ready

```bash
pip install -e '.[cluster]'
gpuctl preflight                     # against current kubeconfig context
gpuctl preflight -o json             # machine-readable
gpuctl snapshot --out cluster.json   # capture for offline analysis
gpuctl preflight --from-file cluster.json
```

Exit codes: `0` healthy, `1` a critical check failed, `2` warnings only.
