# Troubleshooting

Start with `gpuctl preflight`. It names the failing stage; the sections below
map each to a cause and fix.

## `allocatable-gpus` FAIL — GPU nodes present, 0 allocatable GPUs

The most common GPU-on-Kubernetes failure. The device plugin is not advertising
capacity, usually because the driver is not ready.

```bash
kubectl get nodes -L nvidia.com/gpu.present
kubectl -n gpu-operator get pods
kubectl -n gpu-operator logs ds/nvidia-device-plugin-daemonset
kubectl describe node <gpu-node> | grep -A5 Allocatable
```

- If the device plugin pod is `Init`/`CrashLoopBackOff`: the driver is not
  present. With this platform the driver comes from the AMI — confirm the GPU
  node group uses `AL2023_x86_64_NVIDIA` (see `terraform/main.tf`).
- If `nvidia-smi` on the node fails: wrong AMI or instance type without a GPU.

## `gpu-operator` FAIL — no operator pods

```bash
helm list -n gpu-operator
```

Install it (see `helm/gpu-operator/README.md`). If pods exist but aren't ready,
check for taint/toleration mismatches — the operator DaemonSets must tolerate
`nvidia.com/gpu`.

## Pending GPU pods

`gpuctl` reports these as a warning. Inspect the scheduling events:

```bash
kubectl -n gpu-workloads describe pod <pod>
# Events: 0/N nodes are available: N Insufficient nvidia.com/gpu
```

Causes and fixes:

| Event message                              | Cause                          | Fix                                   |
| ------------------------------------------ | ------------------------------ | ------------------------------------- |
| `Insufficient nvidia.com/gpu`              | No free GPUs                   | Scale the GPU node group, or wait     |
| `had untolerated taint {nvidia.com/gpu}`   | Missing toleration             | Add the GPU toleration to the pod     |
| `node(s) didn't match node affinity`       | Missing/incorrect affinity     | Target `nvidia.com/gpu.present=true`  |
| `exceeded quota`                           | Namespace ResourceQuota hit    | Raise the quota or free GPUs          |

The `03-pending-pod-example.yaml` manifest reproduces the first case on purpose.

## `k8s-version` WARN

The control plane is below the tested floor (1.28). Upgrade, or pin a GPU
Operator release that supports the running version.

## gpuctl says "kubernetes package is required"

Live checks need the optional client: `pip install 'gpuctl[cluster]'`. Or work
offline from a captured snapshot: `gpuctl snapshot --out c.json` on a machine
that has access, then `gpuctl preflight --from-file c.json`.
