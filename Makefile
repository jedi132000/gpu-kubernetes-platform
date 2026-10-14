# Convenience targets. All validation here is static/offline (no cloud spend).
.DEFAULT_GOAL := help
HELM_CHART_VERSION ?= v25.3.4

.PHONY: help install test lint type py-check tf-fmt tf-validate helm-template manifests validate

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install the package with dev extras
	pip install -e '.[dev]'

test: ## Run the test suite
	pytest -q

lint: ## Lint Python
	ruff check src tests

type: ## Type-check Python
	mypy

py-check: lint type test ## All Python checks

tf-fmt: ## Check Terraform formatting
	terraform -chdir=terraform fmt -check -recursive

tf-validate: ## Validate Terraform (no backend, no cloud calls)
	terraform -chdir=terraform init -backend=false -input=false
	terraform -chdir=terraform validate

helm-template: ## Render the GPU Operator chart with our overlay
	helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
	helm repo update nvidia
	helm template gpu-operator nvidia/gpu-operator --version $(HELM_CHART_VERSION) \
		-n gpu-operator -f helm/gpu-operator/values.yaml > /dev/null

manifests: ## Schema-validate Kubernetes manifests
	kubeconform -strict -summary kubernetes/

validate: py-check tf-fmt tf-validate manifests ## Everything that runs in CI (except helm)
