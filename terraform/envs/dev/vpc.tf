data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  # first 2 availability zones in the region
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = local.azs
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  # NAT lets private nodes reach the internet (pull images etc).
  # single_nat_gateway = one shared NAT instead of one per AZ, cheaper for a lab
  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  # lets EKS auto-discover which subnets to use for load balancers
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}
