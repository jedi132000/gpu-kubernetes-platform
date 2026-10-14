variable "region" {
  description = "AWS region for the cluster and node groups."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name. Also used as a prefix for related resources."
  type        = string
  default     = "gpu-platform"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}$", var.cluster_name))
    error_message = "cluster_name must be 2-39 chars, lowercase alphanumeric or hyphens, starting with a letter."
  }
}

variable "cluster_version" {
  description = "Kubernetes control-plane version. Keep in sync with gpuctl MIN_K8S_MINOR."
  type        = string
  default     = "1.31"

  validation {
    condition     = can(regex("^1\\.(2[89]|3[0-9])$", var.cluster_version))
    error_message = "cluster_version must be a supported 1.28+ minor (e.g. 1.31)."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across. Must be >= 2 for EKS."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.azs) >= 2
    error_message = "EKS requires subnets in at least two availability zones."
  }
}

variable "gpu_instance_type" {
  description = "EC2 instance type for the GPU node group (must expose NVIDIA GPUs)."
  type        = string
  default     = "g5.xlarge" # 1x NVIDIA A10G, 24 GB
}

variable "gpu_node_min" {
  description = "Minimum GPU nodes. Default 0 so the group can scale to zero when idle."
  type        = number
  default     = 0
}

variable "gpu_node_max" {
  description = "Maximum GPU nodes (ceiling on accelerator cost)."
  type        = number
  default     = 2

  validation {
    condition     = var.gpu_node_max >= var.gpu_node_min
    error_message = "gpu_node_max must be >= gpu_node_min."
  }
}

variable "gpu_node_desired" {
  description = "Desired GPU nodes at apply time."
  type        = number
  default     = 1
}

variable "system_instance_type" {
  description = "Instance type for the CPU system node group (operator, add-ons)."
  type        = string
  default     = "m6i.large"
}

variable "gpu_node_disk_size" {
  description = "Root EBS volume size (GiB) for GPU nodes. GPU AMIs and driver layers are large."
  type        = number
  default     = 100
}

variable "enable_gpu_node_group" {
  description = "Set false to provision only the CPU system group (cheaper validation runs)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to all resources via the provider default_tags."
  type        = map(string)
  default = {
    "project"    = "gpu-kubernetes-platform"
    "managed-by" = "terraform"
  }
}
