output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes control-plane version."
  value       = module.eks.cluster_version
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS control plane."
  value       = module.eks.cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA-based workload identity."
  value       = module.eks.oidc_provider_arn
}

output "vpc_id" {
  description = "VPC ID hosting the cluster."
  value       = module.vpc.vpc_id
}

output "gpu_node_group_enabled" {
  description = "Whether the GPU node group was provisioned."
  value       = var.enable_gpu_node_group
}

output "configure_kubectl" {
  description = "Command to update kubeconfig for this cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}
