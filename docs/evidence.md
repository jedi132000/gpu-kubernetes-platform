# Engineering evidence

Records what was actually executed while building this repository, with
versions and outcomes. It distinguishes static validation (performed) from live
GPU/cloud verification (not performed — no GPU hardware or cloud apply).

## Environment

| Tool        | Version  |
| ----------- | -------- |
| OS          | Windows 11 (CI mirrors on ubuntu-latest) |
| Python      | 3.13.5   |
| Terraform   | 1.9.8    |
| Helm        | 3.16.4   |
| kubeconform | 0.6.7    |
| kubectl     | 1.34.1 (client) |
| AWS provider (resolved) | 5.100.0 |

## Static validation performed

| Check            | Command                                                        | Result |
| ---------------- | -------------------------------------------------------------- | ------ |
| Unit/CLI/manifest tests | `pytest -q`                                             | PASS — 25 passed |
| Lint             | `ruff check src tests`                                         | PASS — all checks passed |
| Type check       | `mypy` (`--strict`)                                            | PASS — no issues in 6 source files |
| Terraform format | `terraform -chdir=terraform fmt -check -recursive`             | PASS |
| Terraform init   | `terraform -chdir=terraform init -backend=false`               | PASS — providers + upstream modules resolved |
| Terraform validate | `terraform -chdir=terraform validate`                        | PASS — configuration is valid |
| Manifest schemas | `kubeconform -strict -summary kubernetes/`                     | PASS — 8/8 resources valid |
| Helm overlay     | `helm template gpu-operator nvidia/gpu-operator --version v25.3.4 -f helm/gpu-operator/values.yaml` | PASS — renders; driver/toolkit disabled, device-plugin/DCGM enabled confirmed in ClusterPolicy |

### Test coverage of cluster states

`pytest` exercises all five states `gpuctl` classifies, against synthetic
snapshots (no live cluster):

- `unreachable` → `api-connectivity` FAIL, exit 1
- `no_gpu_nodes` (CPU-only) → `gpu-nodes` WARN, exit 2
- `missing_operator` → `gpu-operator` FAIL, exit 1
- `unhealthy_gpu` (0 allocatable) → `allocatable-gpus` + `device-plugin` FAIL, exit 1
- `gpu_ready` → all PASS, exit 0

The `gpu_ready` path is also demonstrated end-to-end through the CLI against
`examples/gpu-ready-snapshot.json`.

## Not performed (honest status)

| Item                         | Status        | Why |
| ---------------------------- | ------------- | --- |
| `terraform apply` / live EKS | NOT performed | Would create billable cloud resources; out of scope without explicit authorization. |
| GPU validation Job on hardware | NOT performed | No NVIDIA GPU available in the build environment. The Job is schema-valid and carries correct requests/tolerations/affinity, but "Test PASSED" from `vectorAdd` has not been observed here. |
| GPU Operator live install    | NOT performed | Requires a live cluster. Validated only via `helm template`. |
| MIG / DRA                    | NOT enabled   | Documented as gated future paths. |

## Reproducing

```bash
pip install -e '.[dev]'
./scripts/validate.sh        # runs the sweep above, skipping any missing tool
```
