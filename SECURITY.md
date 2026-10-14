# Security Policy

## Scope

This repository is an infrastructure reference. The most security-relevant
concerns are credential handling, least-privilege access, and not committing
sensitive state. See [docs/security.md](docs/security.md) for the detailed
model.

## Reporting a vulnerability

If you find a security issue in this code (for example, a manifest or Terraform
default that weakens isolation, or a dependency vulnerability), please open a
GitHub security advisory on the repository, or open a regular issue for
non-sensitive reports. Please do not include real credentials, account IDs, or
cluster endpoints in public issues.

We aim to acknowledge reports within a few business days.

## What is in scope

- Insecure-by-default Terraform or Kubernetes configuration.
- Secrets or state accidentally committed to the repository.
- Dependency vulnerabilities in the Python tooling.

## What is out of scope

- Vulnerabilities in upstream projects (AWS, EKS, the NVIDIA GPU Operator,
  Terraform providers) — report those to the respective projects. We will
  update pinned versions in response.
- Cost or capacity issues from running the full GPU path; these are documented,
  not vulnerabilities.
