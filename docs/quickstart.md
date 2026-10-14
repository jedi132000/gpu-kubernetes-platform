# Quickstart

Two paths: a **CPU-only** path that works on any cluster (no GPU, no cloud
spend) to exercise the scheduling model and `gpuctl`, and the **full GPU on
EKS** path.

## Prerequisites

| Tool      | Version tested | Needed for            |
| --------- | -------------- | --------------------- |
| python    | 3.10+ (3.13)   | gpuctl                |
| kubectl   | 1.28+ (1.34)   | applying manifests    |
| helm      | 3.14+ (3.16)   | GPU Operator install  |
| terraform | 1.6+ (1.9)     | EKS provisioning      |
| aws cli   | 2.x            | EKS auth (GPU path)   |

## Path A — CPU-only (no GPU, no cloud)

Works against kind, minikube, or any existing cluster.

```bash
# 1. Install the preflight CLI
pip install -e '.[cluster]'

# 2. Apply the scheduling model and the CPU demo
kubectl apply -f kubernetes/scheduling/00-namespace-quota.yaml
kubectl apply -f kubernetes/scheduling/01-priorityclasses.yaml
kubectl apply -f kubernetes/cpu-demo/cpu-workload.yaml

# 3. Run preflight — expect state "no_gpu_nodes" (exit code 2)
gpuctl preflight
```

`gpuctl` correctly reports a CPU-only cluster as a warning, not a failure.

## Path B — full GPU on EKS

> **Cost warning.** This provisions a NAT gateway, an EKS control plane
> (hourly), and at least one `g5.xlarge` GPU instance. Expect real charges.
> Tear down when done (below). Do not run `terraform apply` without intent.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # edit region/name as needed
terraform init
terraform plan -out tfplan                      # review before applying
terraform apply tfplan

# Configure kubectl from the output
$(terraform output -raw configure_kubectl)
cd ..

# Install the GPU Operator (driver/toolkit come from the AMI)
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia && helm repo update
helm upgrade --install gpu-operator nvidia/gpu-operator \
  --version v25.3.4 -n gpu-operator --create-namespace \
  -f helm/gpu-operator/values.yaml

# Wait for the device plugin, then validate
kubectl -n gpu-operator rollout status ds/nvidia-device-plugin-daemonset
gpuctl preflight                                # expect state "gpu_ready"

# Run the real GPU validation job
kubectl apply -f kubernetes/scheduling/00-namespace-quota.yaml
kubectl apply -f kubernetes/scheduling/01-priorityclasses.yaml
kubectl apply -f kubernetes/scheduling/02-gpu-validation-job.yaml
kubectl -n gpu-workloads logs job/gpu-vectoradd-validation
# -> "Test PASSED"
```

## Teardown

```bash
kubectl delete -f kubernetes/scheduling/ --ignore-not-found
helm uninstall gpu-operator -n gpu-operator
cd terraform && terraform destroy
```

Destroying the Terraform stack removes the GPU instances, NAT gateway, and
control plane — this is what stops the ongoing charges.
