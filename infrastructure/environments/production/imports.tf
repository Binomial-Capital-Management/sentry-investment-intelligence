# =============================================================================
# Production Import Blocks
# =============================================================================
# These import blocks bring existing AWS resources under Terraform management.
# After running `terraform plan` and verifying no changes, these can be removed
# or kept for documentation purposes.
#
# Run order:
#   1. terraform init
#   2. terraform plan (verify imports show correctly)
#   3. terraform apply (import resources)
#   4. terraform plan (should show 0 changes)
# =============================================================================

# -----------------------------------------------------------------------------
# Day 2: Networking + Storage Imports
# -----------------------------------------------------------------------------

# VPC
import {
  to = aws_vpc.main
  id = "<VPC_ID>"
}

# Internet Gateway
import {
  to = aws_internet_gateway.main
  id = "igw-0f8bb1ed9636508f3"
}

# Subnets
import {
  to = aws_subnet.private_1
  id = "<SUBNET_ID>"
}

import {
  to = aws_subnet.public_1
  id = "<SUBNET_ID>"
}

import {
  to = aws_subnet.private_2
  id = "<SUBNET_ID>"
}

import {
  to = aws_subnet.public_2
  id = "<SUBNET_ID>"
}

# Security Groups
import {
  to = aws_security_group.alb
  id = "<SECURITY_GROUP_ID>"
}

import {
  to = aws_security_group.ecs
  id = "<SECURITY_GROUP_ID>"
}

import {
  to = aws_security_group.rds
  id = "<SECURITY_GROUP_ID>"
}

import {
  to = aws_security_group.efs
  id = "<SECURITY_GROUP_ID>"
}

# S3 Buckets
import {
  to = aws_s3_bucket.frontend
  id = "binomial-sentry-frontend-bcm001"
}

import {
  to = aws_s3_bucket.artifacts
  id = "binomial-artifacts-prod"
}

# EFS
import {
  to = aws_efs_file_system.main
  id = "<EFS_ID>"
}

import {
  to = aws_efs_access_point.main
  id = "<EFS_ACCESS_POINT_ID>"
}

# -----------------------------------------------------------------------------
# Day 3: Compute + CDN Imports
# -----------------------------------------------------------------------------

# ECS Cluster
import {
  to = aws_ecs_cluster.main
  id = "binomial-sentry-cluster"
}

# ECR Repository
import {
  to = aws_ecr_repository.backend
  id = "binomial-sentry-backend"
}

# CloudWatch Log Group
import {
  to = aws_cloudwatch_log_group.ecs
  id = "/ecs/binomial-sentry-backend"
}

# Route53 Zone
import {
  to = aws_route53_zone.main
  id = "<ROUTE53_ZONE_ID>"
}

# -----------------------------------------------------------------------------
# Day 3: ALB Imports
# -----------------------------------------------------------------------------

# Application Load Balancer
import {
  to = aws_lb.main
  id = "arn:aws:elasticloadbalancing:us-east-1:<AWS_ACCOUNT_ID>:loadbalancer/app/binomial-sentry-backend-alb/cc890438e2b72dcb"
}

# Target Group
import {
  to = aws_lb_target_group.main
  id = "arn:aws:elasticloadbalancing:us-east-1:<AWS_ACCOUNT_ID>:targetgroup/binomial-sentry-backend-tg/9640c568bc7f417e"
}

# HTTP Listener (port 80)
import {
  to = aws_lb_listener.http
  id = "arn:aws:elasticloadbalancing:us-east-1:<AWS_ACCOUNT_ID>:listener/app/binomial-sentry-backend-alb/cc890438e2b72dcb/86b23de451f77227"
}

# HTTPS Listener (port 443)
import {
  to = aws_lb_listener.https
  id = "arn:aws:elasticloadbalancing:us-east-1:<AWS_ACCOUNT_ID>:listener/app/binomial-sentry-backend-alb/cc890438e2b72dcb/ce24fa7dbca225cd"
}

# CloudFront Distribution
import {
  to = aws_cloudfront_distribution.main
  id = "E12K8DUMY7C9U9"
}

# -----------------------------------------------------------------------------
# Day 4: Aurora Database Imports
# -----------------------------------------------------------------------------

# DB Subnet Group
import {
  to = aws_db_subnet_group.main
  id = "default-<VPC_ID>"
}

# Aurora Cluster
import {
  to = aws_rds_cluster.main
  id = "binomial-sentry-cluster"
}

# Aurora Instance 1 (Primary)
import {
  to = aws_rds_cluster_instance.instance_1
  id = "binomial-sentry-cluster-instance-1"
}

# Aurora Instance 2 (Replica)
import {
  to = aws_rds_cluster_instance.instance_2
  id = "binomial-sentry-cluster-instance-1-us-east-1a"
}

# -----------------------------------------------------------------------------
# Day 4: ECS Service Import
# -----------------------------------------------------------------------------
import {
  to = aws_ecs_service.main
  id = "binomial-sentry-cluster/binomial-sentry-backend-service-b9ze202w"
}

# -----------------------------------------------------------------------------
# Additional Imports: NAT Gateway
# -----------------------------------------------------------------------------

# Elastic IP for NAT Gateway
import {
  to = aws_eip.nat
  id = "eipalloc-0b76150dbaae23183"
}

# NAT Gateway
import {
  to = aws_nat_gateway.main
  id = "nat-0a22b81cd8f5f95ed"
}

# -----------------------------------------------------------------------------
# ElastiCache Redis Imports
# -----------------------------------------------------------------------------

# Redis Subnet Group
import {
  to = aws_elasticache_subnet_group.redis
  id = "binomial-sentry-redis-cache"
}

# Redis Replication Group
import {
  to = aws_elasticache_replication_group.redis
  id = "binomial-redis"
}

# -----------------------------------------------------------------------------
# Route Tables Imports
# -----------------------------------------------------------------------------
import {
  to = aws_route_table.private
  id = "rtb-06ec01c6b64611d56"
}

import {
  to = aws_route_table.public
  id = "rtb-0711c7019f28ffd7c"
}

# Route table associations - format: subnet-id/route-table-id
# NOTE: Only private_2 has an explicit association. Other subnets use the VPC main route table.
import {
  to = aws_route_table_association.private_2
  id = "<SUBNET_ID>/rtb-06ec01c6b64611d56"
}

# -----------------------------------------------------------------------------
# VPC Endpoint Import
# -----------------------------------------------------------------------------
import {
  to = aws_vpc_endpoint.s3
  id = "vpce-0e9eba180b9c24fd1"
}

# -----------------------------------------------------------------------------
# EFS Mount Targets Imports
# -----------------------------------------------------------------------------
import {
  to = aws_efs_mount_target.private_1a
  id = "fsmt-0ee96c3a89c8c7a34"
}

import {
  to = aws_efs_mount_target.public_1b
  id = "fsmt-01a69a7e0371727e6"
}

# -----------------------------------------------------------------------------
# GitHub Actions OIDC Imports
# -----------------------------------------------------------------------------

import {
  to = aws_iam_openid_connect_provider.github_actions
  id = "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
}

import {
  to = aws_iam_role.github_actions_deploy
  id = "github-actions-deploy"
}

import {
  to = aws_iam_role_policy.github_actions_deploy
  id = "github-actions-deploy:DeployPolicy"
}

import {
  to = aws_iam_role.github_actions_terraform
  id = "github-actions-terraform"
}

import {
  to = aws_iam_role_policy_attachment.github_actions_terraform
  id = "github-actions-terraform/arn:aws:iam::aws:policy/AdministratorAccess"
}

# -----------------------------------------------------------------------------
# Lambda Functions - NOT IMPORTED
# -----------------------------------------------------------------------------
# Lambda functions use AWS-managed S3 for code storage and are deployed
# via their own CI/CD pipeline. They cannot be cleanly imported to Terraform.
# Functions: earnings-ipo-calendar, fear-greed-index
