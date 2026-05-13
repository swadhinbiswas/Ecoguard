# Terraform module for deploying Eco-Guard on AWS EKS + RDS

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
    helm   = { source = "hashicorp/helm", version = "~> 2.14" }
  }
}

variable "region"            { default = "us-east-1" }
variable "cluster_name"      { default = "eco-guard" }
variable "node_count"        { default = 2 }
variable "node_instance"     { default = "g5.xlarge" }
variable "db_instance"       { default = "db.t4g.medium" }
variable "db_password"       { sensitive = true }
variable "jwt_secret"        { sensitive = true }
variable "admin_password"    { sensitive = true }
variable "domain"            { default = "ecoguard.example.com" }
variable "model_bucket"      { default = "ecoguard-models" }

# ── VPC + Networking ────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0"
  name    = var.cluster_name
  cidr    = "10.0.0.0/16"
  azs     = ["${var.region}a", "${var.region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
}

# ── RDS PostgreSQL ──────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier     = var.cluster_name
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.db_instance
  allocated_storage = 20
  db_name        = "ecoguard"
  username       = "ecoguard"
  password       = var.db_password
  skip_final_snapshot = true
  storage_encrypted   = true
}

# ── EKS Cluster ─────────────────────────────────────────────
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.0"
  cluster_name    = var.cluster_name
  cluster_version = "1.30"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  eks_managed_node_groups = {
    main = {
      instance_types = [var.node_instance]
      desired_size   = var.node_count
      max_size       = 5
      min_size       = 1
    }
  }
}

# ── S3 Model Storage ────────────────────────────────────────
resource "aws_s3_bucket" "models" {
  bucket = var.model_bucket
}

# ── Helm Deploy ─────────────────────────────────────────────
resource "helm_release" "eco_guard" {
  name       = "eco-guard"
  chart      = "../../helm/eco-guard"
  repository = null

  set {
    name  = "secrets.databaseUrl"
    value = "postgresql+asyncpg://ecoguard:${var.db_password}@${aws_db_instance.postgres.endpoint}/ecoguard?sslmode=require"
  }
  set { name = "secrets.jwtSecret";     value = var.jwt_secret }
  set { name = "secrets.adminPassword"; value = var.admin_password }
  set { name = "ingress.host";          value = var.domain }
  set { name = "redis.enabled";         value = "true" }
}

output "eks_endpoint"   { value = module.eks.cluster_endpoint }
output "db_endpoint"    { value = aws_db_instance.postgres.endpoint }
output "dashboard_url"  { value = "https://${var.domain}/dashboard" }
