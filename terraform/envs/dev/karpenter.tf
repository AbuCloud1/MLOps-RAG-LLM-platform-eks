# IAM plumbing for karpenter: controller role (IRSA) + node role, using the
# official submodule from the same repo as the eks module. create_access_entry
# defaults to true, so the node role can join the cluster with no extra config
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 20.0"

  cluster_name = module.eks.cluster_name

  enable_v1_permissions = true

  enable_irsa            = true
  irsa_oidc_provider_arn = module.eks.oidc_provider_arn

  node_iam_role_name            = "${var.cluster_name}-karpenter-node"
  node_iam_role_use_name_prefix = false
}
