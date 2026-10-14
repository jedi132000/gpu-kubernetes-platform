#!/usr/bin/env bash
# Run the full static validation sweep locally (no cloud spend, no GPU needed).
# Mirrors .github/workflows/ci.yml. Skips any tool that is not installed and
# reports it, rather than failing silently.
set -euo pipefail

HELM_CHART_VERSION="${HELM_CHART_VERSION:-v25.3.4}"
cd "$(dirname "$0")/.."

have() { command -v "$1" >/dev/null 2>&1; }
skipped=()

echo "== Python: ruff / mypy / pytest =="
if have python; then
  python -m ruff check src tests
  python -m mypy
  python -m pytest -q
else
  skipped+=("python")
fi

echo "== Terraform: fmt / validate =="
if have terraform; then
  terraform -chdir=terraform fmt -check -recursive
  terraform -chdir=terraform init -backend=false -input=false >/dev/null
  terraform -chdir=terraform validate
else
  skipped+=("terraform")
fi

echo "== Kubernetes: kubeconform =="
if have kubeconform; then
  kubeconform -strict -summary kubernetes/
else
  skipped+=("kubeconform")
fi

echo "== Helm: template GPU Operator overlay =="
if have helm; then
  helm repo add nvidia https://helm.ngc.nvidia.com/nvidia >/dev/null 2>&1 || true
  helm repo update nvidia >/dev/null
  helm template gpu-operator nvidia/gpu-operator --version "${HELM_CHART_VERSION}" \
    -n gpu-operator -f helm/gpu-operator/values.yaml >/dev/null
  echo "helm template OK"
else
  skipped+=("helm")
fi

if [ ${#skipped[@]} -gt 0 ]; then
  echo
  echo "SKIPPED (not installed): ${skipped[*]}"
fi
echo "Validation sweep complete."
