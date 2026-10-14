# Security considerations

## Credentials and state

- No AWS credentials, kubeconfig, tokens, or Terraform state are committed. See
  the repository `.gitignore`; CI also runs secret scanning.
- Terraform state is expected in a remote backend (S3 + lock table) configured
  per environment via `terraform init -backend-config`. State contains
  sensitive values and must never be committed.
- The `gpuctl` preflight is **read-only**: it lists nodes/pods and never mutates
  the cluster. Snapshots contain cluster metadata only (no Secret contents).

## Least privilege

- EKS access is IAM/IRSA based. The Terraform grants the cluster creator admin
  (`enable_cluster_creator_admin_permissions`) for first-run convenience;
  production should replace this with scoped access entries.
- GPU workloads run with `allowPrivilegeEscalation: false` and dropped
  capabilities. The CUDA sample image runs as root (documented inline in
  `02-gpu-validation-job.yaml`); production inference images should run as a
  non-root user like the CPU demo does.
- The namespace enforces the `baseline` Pod Security Standard.

## Node isolation

GPU nodes are tainted so only workloads that explicitly tolerate
`nvidia.com/gpu` can schedule there. This both prevents accelerator waste and
limits which workloads share a GPU host.

## CI permissions

GitHub Actions workflows request least-privilege token scopes
(`contents: read`) and do **not** carry cloud credentials. Infrastructure
provisioning is never part of automated public CI — only static validation
(`terraform validate`, `helm template`, `kubeconform`, tests) runs there.

## Reporting

See [`SECURITY.md`](../SECURITY.md) at the repository root for how to report a
vulnerability.
