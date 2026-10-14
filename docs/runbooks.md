# Operational runbooks

Concise, action-first runbooks for the failure modes this platform is designed
to handle. Each assumes `gpuctl` and `kubectl` access to the affected cluster.

## RB-1: GPU node reports zero allocatable GPUs

**Symptom:** `gpuctl preflight` → `allocatable-gpus` FAIL; workloads Pending.

1. Confirm scope: `kubectl get nodes -L nvidia.com/gpu.present`.
2. Check the device plugin: `kubectl -n gpu-operator get pods -o wide | grep device-plugin`.
3. If the plugin is not Running, check driver readiness on the node
   (`nvidia-smi` via a debug pod or SSM). Driver comes from the AMI here.
4. If a single node is bad, cordon and recycle it:
   `kubectl cordon <node>` → drain GPU pods → terminate the instance; the ASG
   replaces it with a correctly-initialised node.
5. Verify recovery: `gpuctl preflight` → `gpu_ready`.

## RB-2: GPU Operator degraded after an upgrade

**Symptom:** operator or NFD pods not ready after a Helm upgrade.

1. `helm history gpu-operator -n gpu-operator` to see revisions.
2. Inspect the failing component's logs in the `gpu-operator` namespace.
3. Roll back: `helm rollback gpu-operator <previous-revision> -n gpu-operator`.
4. Re-run `gpuctl preflight`. File an issue capturing the chart version diff.

## RB-3: GPU pods Pending under contention

**Symptom:** `pending-gpu-pods` WARN; inference latency rising.

1. Identify demand vs. capacity: compare pending GPU pods to
   `gpuctl preflight -o json` (`allocatable-gpus`).
2. Short term: ensure latency-sensitive pods use `gpu-inference-high` so they
   preempt `gpu-batch-low` training jobs.
3. Medium term: raise `gpu_node_max` and re-apply Terraform, or enable cluster
   autoscaling on the GPU node group.
4. Confirm the namespace ResourceQuota is not the binding constraint
   (`kubectl -n <ns> describe resourcequota`).

## RB-4: Suspected driver/runtime mismatch

**Symptom:** GPU containers fail to start with CUDA/driver errors even though
the node has a GPU.

1. Confirm the node AMI is the GPU variant (`AL2023_x86_64_NVIDIA`).
2. Confirm the operator is **not** also managing a driver
   (`driver.enabled` must be `false` in the ClusterPolicy) — two drivers
   conflict. See ADR 0001.
3. If the AMI driver is too old for the CUDA image, rotate the node group to a
   newer AMI release rather than enabling the operator driver.

## Escalation

Capture a snapshot for the record before escalating:

```bash
gpuctl snapshot --out incident-$(date +%s).json
```

The snapshot is read-only cluster metadata (no secrets) and can be attached to
an incident ticket for offline analysis with `gpuctl preflight --from-file`.
