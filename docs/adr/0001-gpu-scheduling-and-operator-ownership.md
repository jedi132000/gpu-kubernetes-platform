# ADR 0001: GPU scheduling model and operator/driver ownership

- Status: Accepted
- Date: 2026-02

## Context

An EKS cluster that runs GPU workloads needs a clear answer to two questions:

1. **How are GPUs scheduled?** Whole-GPU via the device plugin, fractional via
   MIG, or the newer Dynamic Resource Allocation (DRA) API.
2. **Who owns the NVIDIA driver and container runtime?** The node AMI, or the
   GPU Operator.

Getting this wrong produces the two most common GPU-on-Kubernetes failures we
want this reference to avoid: GPUs that never become `allocatable` (driver /
device-plugin mismatch) and ordinary pods consuming expensive GPU nodes.

## Decision

**Scheduling:** whole-GPU via the NVIDIA device plugin. Pods request the
integer extended resource `nvidia.com/gpu`. GPU nodes are dedicated with a
`nvidia.com/gpu=present:NoSchedule` taint and labelled `nvidia.com/gpu.present=true`;
GPU pods must carry a matching toleration and node affinity.

**Driver/runtime ownership:** the GPU node group uses the AWS GPU-optimized AMI
(`AL2023_x86_64_NVIDIA`), which ships the NVIDIA driver and container runtime.
The GPU Operator therefore runs with `driver.enabled=false` and
`toolkit.enabled=false`, owning only Node Feature Discovery, the device plugin,
and DCGM Exporter.

## Alternatives considered

- **Operator-managed driver on a plain AMI** (`driver.enabled=true`). More
  portable across clouds and lets you pin a driver independent of the AMI, but
  adds a privileged driver-container build/boot step and a longer, more
  failure-prone node bring-up. Rejected for an EKS-centric reference where the
  AWS GPU AMI is well maintained.
- **MIG partitioning.** Useful for packing many small inference tenants onto
  A100/H100. Rejected as a default because the reference targets `g5.xlarge`
  (A10G), which does not support MIG. Left as an opt-in, hardware-gated path.
- **Dynamic Resource Allocation (DRA).** The strategic direction for
  structured/partitionable accelerators. Rejected for now because support
  across managed Kubernetes and the NVIDIA stack was still maturing at the time
  of writing; the device-plugin model is the compatible choice. Revisit when
  DRA is GA and supported on EKS.

## Consequences

- Driver upgrades are tied to AMI/node-group updates, not a Helm value. Node
  rotation is the upgrade path.
- Exactly one component advertises `nvidia.com/gpu`; the `gpuctl allocatable-gpus`
  check will catch the misconfiguration where GPU nodes show zero GPUs.
- The DCGM Exporter deployed by the operator is the telemetry contract consumed
  by the companion `gpu-observability-stack` repository.
- Switching to operator-managed drivers later means a plain AMI plus flipping
  two Helm values — isolated, documented, reversible.
