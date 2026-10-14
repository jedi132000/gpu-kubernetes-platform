# AGENTS.md

Guidance for AI agents and contributors working in this repository. It
describes how the code is organised, how to validate changes, and what must not
change casually.

## Layout

```
terraform/            EKS + VPC + node groups (upstream modules). versions/variables/main/outputs.
helm/gpu-operator/    Values overlay for the upstream GPU Operator chart + install doc.
kubernetes/
  scheduling/         Namespace+quota, priority classes, GPU validation job, pending-pod example.
  cpu-demo/           CPU-only workload (no GPU request, avoids GPU nodes).
src/gpuctl/           Preflight CLI. models.py (data) -> checks.py (pure) -> kube.py (I/O) -> cli.py.
tests/                pytest: test_models, test_checks, test_cli, test_manifests. conftest has fixtures.
docs/                 architecture, quickstart, troubleshooting, runbooks, security, adr/, metadata, evidence.
```

## Conventions

- **gpuctl layering is deliberate.** `checks.py` must stay pure (no I/O): it
  takes a `ClusterSnapshot` and returns `CheckResult`s. Only `kube.py` imports
  the `kubernetes` client, and that import is lazy so the package works without
  it. Keep it that way — it is what makes the state matrix testable.
- Python: type hints everywhere; `ruff` + `mypy --strict` must pass.
- New checks: add the function to `checks.py`, append it to `ALL_CHECKS`, and
  cover every status it can emit in `tests/test_checks.py`.
- Manifests: every workload must be valid under `kubeconform -strict` and obey
  the invariants in `tests/test_manifests.py`.

## Build / validate commands

```bash
pip install -e '.[dev]'
pytest -q
ruff check src tests
mypy
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false && terraform -chdir=terraform validate
helm template gpu-operator nvidia/gpu-operator --version v25.3.4 -f helm/gpu-operator/values.yaml
kubeconform -strict kubernetes/
```

CI (`.github/workflows/ci.yml`) runs the same checks.

## Testing expectations

- Unit tests cover all five cluster states (unreachable, no_gpu_nodes,
  missing_operator, unhealthy_gpu, gpu_ready) and the resulting exit codes.
- Do not weaken a test to make a change pass. If behaviour legitimately
  changes, update the test and explain why in the commit.
- Tests must not require a live cluster, cloud credentials, or a GPU.

## Security rules

- Never commit AWS credentials, kubeconfig, tokens, `*.tfstate`, `*.tfvars`
  (the `.example` is fine), or captured snapshots. `.gitignore` enforces this;
  do not relax it.
- CI must not gain cloud credentials or run `terraform apply`. Keep workflow
  token scopes minimal (`contents: read`).
- `gpuctl` must remain read-only against clusters.

## Do not change casually

- The driver-ownership decision (`driver.enabled=false`, AMI owns the driver).
  Changing it means updating `terraform/main.tf` (AMI type), the Helm values,
  and ADR 0001 together — they are a set.
- The GPU node taint/label keys (`nvidia.com/gpu`, `nvidia.com/gpu.present`):
  they are referenced by Terraform, the manifests, and `gpuctl`. Change in one
  place and the others break silently.
- Pinned versions (Kubernetes, GPU Operator) — bump deliberately and re-run the
  full validation sweep, then update the compatibility table and evidence.
