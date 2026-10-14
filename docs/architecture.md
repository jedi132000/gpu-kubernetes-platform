# Architecture

## Components

```mermaid
flowchart TB
  subgraph AWS["AWS account"]
    subgraph VPC["VPC (terraform-aws-modules/vpc)"]
      subgraph EKS["EKS cluster (terraform-aws-modules/eks)"]
        CP["Control plane\nk8s 1.31"]
        subgraph SYS["System node group (CPU)\nAL2023_x86_64_STANDARD"]
          OP["GPU Operator\n(NFD, device plugin, DCGM)"]
          ADDON["coredns / kube-proxy / vpc-cni"]
        end
        subgraph GPU["GPU node group (tainted)\nAL2023_x86_64_NVIDIA, g5.xlarge"]
          DP["nvidia-device-plugin"]
          DCGM["dcgm-exporter"]
          WL["GPU workloads\n(request nvidia.com/gpu)"]
        end
      end
    end
  end

  DEV["gpuctl preflight"] -->|read-only API| CP
  OP --> DP
  OP --> DCGM
  DP -->|advertises nvidia.com/gpu| CP
  WL -->|toleration + affinity| GPU
```

## Scheduling model

- GPU nodes are **dedicated** via a `nvidia.com/gpu=present:NoSchedule` taint.
  Only pods with a matching toleration land on them.
- GPU nodes are **labelled** `nvidia.com/gpu.present=true` (by the node group
  and by Node Feature Discovery). GPU workloads use required node affinity on
  this label.
- The NVIDIA **device plugin** advertises `nvidia.com/gpu` as an integer
  resource. Pods request whole GPUs; GPUs cannot be overcommitted.
- A namespace **ResourceQuota** caps GPUs per tenant; a **LimitRange** supplies
  a default GPU request so malformed pods are rejected.
- **PriorityClasses** let inference serving preempt batch training when the GPU
  pool is contended.

See [adr/0001](adr/0001-gpu-scheduling-and-operator-ownership.md) for why this
model (and the AMI-owns-driver split) was chosen.

## Preflight flow

```mermaid
sequenceDiagram
  participant U as operator
  participant G as gpuctl
  participant K as kube-apiserver
  U->>G: gpuctl preflight
  G->>K: list nodes, operator pods, pending pods (read-only)
  K-->>G: snapshot
  G->>G: run checks -> classify state
  G-->>U: report + exit code (0 ready / 1 critical / 2 warnings)
```

`gpuctl` classifies the cluster into one of: `unreachable`, `no_gpu_nodes`
(CPU-only), `missing_operator`, `unhealthy_gpu`, or `gpu_ready`.

## Component boundaries

| Concern                         | Owner                              |
| ------------------------------- | ---------------------------------- |
| VPC, subnets, IAM, EKS, nodes   | Terraform (`terraform/`)           |
| NVIDIA driver + container runtime | GPU node AMI                     |
| device plugin, NFD, DCGM        | GPU Operator (`helm/gpu-operator`) |
| quotas, priority, placement     | manifests (`kubernetes/`)          |
| validation / diagnostics        | `gpuctl` (`src/gpuctl`)            |
| telemetry dashboards + alerts   | companion `gpu-observability-stack` |
