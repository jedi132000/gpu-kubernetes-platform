# GPU-aware EKS reference.
#
# Uses the upstream terraform-aws-modules for VPC and EKS rather than
# re-implementing control-plane and networking internals; see
# docs/adr/0001 for the ownership rationale. Two node groups:
#
#   * system (CPU)  - runs the GPU Operator, add-ons and CPU workloads.
#   * gpu (tainted) - runs only accelerator workloads that tolerate the taint.
#
# The GPU node group uses an AWS GPU-optimized AMI that ships the NVIDIA
# driver and container runtime, so the GPU Operator runs with driver and
# toolkit management disabled (helm/gpu-operator/values.yaml).

data "aws_caller_identity" "current" {}

locals {
  # Standard subnet tags that let the AWS cloud controller and future load
  # balancers discover the right subnets.
  cluster_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = var.azs

  private_subnets = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # one NAT GW to reduce cost in a reference environment
  enable_dns_hostnames = true

  public_subnet_tags = merge(local.cluster_tags, {
    "kubernetes.io/role/elb" = "1"
  })
  private_subnet_tags = merge(local.cluster_tags, {
    "kubernetes.io/role/internal-elb" = "1"
  })
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.24"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Grant the identity running Terraform cluster-admin so `kubectl` and the
  # Helm install step work immediately after apply.
  enable_cluster_creator_admin_permissions = true

  # Core add-ons managed by EKS. The GPU stack (device plugin, DCGM) is owned
  # by the GPU Operator Helm chart, not by EKS add-ons, to keep one owner.
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
  }

  eks_managed_node_groups = {
    system = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.system_instance_type]
      min_size       = 1
      max_size       = 3
      desired_size   = 2
      labels = {
        "workload-class" = "system"
      }
    }

    gpu = {
      create = var.enable_gpu_node_group

      # AWS GPU-optimized AMI: bundles the NVIDIA driver + container runtime.
      ami_type       = "AL2023_x86_64_NVIDIA"
      instance_types = [var.gpu_instance_type]

      min_size     = var.gpu_node_min
      max_size     = var.gpu_node_max
      desired_size = var.gpu_node_desired

      disk_size = var.gpu_node_disk_size

      labels = {
        "workload-class"         = "gpu"
        "nvidia.com/gpu.present" = "true"
      }

      # Dedicate GPU nodes: only pods that explicitly tolerate this taint land
      # here, so ordinary workloads cannot consume accelerator capacity.
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "present"
          effect = "NO_SCHEDULE"
        }
      }

      tags = {
        "workload-class" = "gpu"
      }
    }
  }

  tags = var.tags
}
