output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "region" {
  description = "Region the cluster lives in"
  value       = var.region
}

output "update_kubeconfig_command" {
  description = "Run this to point kubectl at the new cluster"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}
