# Examples

## `gpu-ready-snapshot.json`

A captured `gpuctl` snapshot of a healthy GPU cluster (one GPU node, one system
node, operator + device plugin + DCGM running). Use it to see what a passing
preflight looks like without any cluster:

```bash
gpuctl preflight --from-file examples/gpu-ready-snapshot.json
# -> every check PASS, state: gpu_ready, exit 0
```

This is the same JSON shape that `gpuctl snapshot` writes from a live cluster,
so you can capture one environment and analyse it elsewhere:

```bash
gpuctl snapshot --out mycluster.json          # on a machine with cluster access
gpuctl preflight --from-file mycluster.json    # anywhere
```

Snapshots contain cluster metadata only (node labels/taints, pod readiness) —
no Secret contents — but may include internal node names, so they are
`.gitignore`d by default. The example here uses placeholder names.

## Workload manifests

The scheduling examples under [`../kubernetes`](../kubernetes) double as
examples: the CPU demo runs anywhere, and `03-pending-pod-example.yaml`
intentionally reproduces an unschedulable GPU request for practising the
pending-pod diagnostic flow (see [../docs/troubleshooting.md](../docs/troubleshooting.md)).
