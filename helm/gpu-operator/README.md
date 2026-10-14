# NVIDIA GPU Operator install

This directory holds a values overlay for the upstream
[`nvidia/gpu-operator`](https://github.com/NVIDIA/gpu-operator) Helm chart. We
do not vendor the chart; we pin a version and override only what this platform
needs.

## Pinned version

| Component     | Version  | Notes                                             |
| ------------- | -------- | ------------------------------------------------- |
| gpu-operator  | v25.3.4  | Chart + app version. Validated with `helm template`. |

## Ownership model

The GPU node group (see `terraform/`) runs an **AWS GPU-optimized AMI**
(`AL2023_x86_64_NVIDIA`) that ships the NVIDIA driver and container runtime.
To avoid two systems managing the driver, the operator runs with:

- `driver.enabled=false` — driver comes from the AMI.
- `toolkit.enabled=false` — container runtime comes from the AMI.

and owns the device plugin, Node Feature Discovery, and DCGM Exporter. The
rationale and the alternative (operator-managed driver on a plain AMI) are in
[`docs/adr/0001-gpu-scheduling-and-operator-ownership.md`](../../docs/adr/0001-gpu-scheduling-and-operator-ownership.md).

## Install

```bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

helm upgrade --install gpu-operator nvidia/gpu-operator \
  --version v25.3.4 \
  --namespace gpu-operator --create-namespace \
  -f helm/gpu-operator/values.yaml
```

Verify rollout, then run the platform preflight:

```bash
kubectl -n gpu-operator rollout status ds/nvidia-device-plugin-daemonset
gpuctl preflight
```

## Device plugin vs. Dynamic Resource Allocation (DRA)

This platform uses the **device-plugin** model: the NVIDIA device plugin
advertises `nvidia.com/gpu` as an integer extended resource, and pods request
whole GPUs. Kubernetes DRA (`resource.k8s.io`) is the newer, more expressive
API for structured/partitionable accelerators and is still maturing across
managed providers. We stay on the device-plugin model for broad EKS
compatibility; DRA is noted as a future direction in the ADR.

## MIG

MIG (Multi-Instance GPU) is **off by default** (`mig.strategy=none`). It only
applies to MIG-capable hardware (A100/H100 class) — not the default
`g5.xlarge` (A10G). Enabling it is hardware-specific; do not turn it on for
instances that do not support it.
