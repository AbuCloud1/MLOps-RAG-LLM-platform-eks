variable "region" {
  description = "AWS region to build in"
  type        = string
  default     = "eu-west-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "abubker-eks-lab"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}
