module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  # need to reach the API server from a laptop, so keep the endpoint public
  cluster_endpoint_public_access = true

  # gives the identity running terraform (the SSO admin role) cluster-admin,
  # otherwise kubectl is locked out after creation
  enable_cluster_creator_admin_permissions = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # core addons, versions resolved automatically.
  # aws-ebs-csi-driver needs an IAM role (below) to call the EBS API
  # and create volumes for PVCs.
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
    aws-ebs-csi-driver = {
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  eks_managed_node_groups = {
    # Qdrant, the retrieval app and monitoring run on these
    cpu = {
      instance_types = ["t3.large"]
      min_size       = 2
      max_size       = 3
      desired_size   = 2
    }

    # one g4dn.xlarge = one NVIDIA T4 GPU, AL2_x86_64_GPU AMI ships
    # with NVIDIA drivers preinstalled. taint keeps normal pods off
    # the pricey GPU node - only pods tolerating nvidia.com/gpu land here
    gpu = {
      ami_type       = "AL2_x86_64_GPU"
      instance_types = ["g4dn.xlarge"]
      min_size       = 1
      max_size       = 1
      desired_size   = 1

      # the vLLM image (~8GB) plus the model download overflow the default
      # 20GB root disk and the kubelet evicts the pod (DiskPressure). this
      # module uses a launch template, so disk size has to go through
      # block_device_mappings - the top-level disk_size attribute is ignored
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            delete_on_termination = true
          }
        }
      }

      labels = {
        "nvidia.com/gpu" = "true"
      }

      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }
}

# IAM role for the EBS CSI driver, scoped to just that service account.
# IRSA: the pod assumes this role via the cluster's OIDC provider,
# no long-lived keys needed
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${var.cluster_name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}
