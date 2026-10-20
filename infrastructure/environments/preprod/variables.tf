# =============================================================================
# Pre-Production Environment Variables
# =============================================================================

# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------
variable "environment" {
  description = "Environment name"
  type        = string
  default     = "preprod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "binomial-sentry"
}

# -----------------------------------------------------------------------------
# VPC & Networking (Shared with Production)
# -----------------------------------------------------------------------------
variable "vpc_id" {
  description = "Existing VPC ID (shared with production)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs (shared with production)"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs (shared with production)"
  type        = list(string)
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# -----------------------------------------------------------------------------
# ECS Configuration (Smaller than Production)
# -----------------------------------------------------------------------------
variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
  default     = "binomial-sentry-cluster-preprod"
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
  default     = "binomial-sentry-backend-service-preprod"
}

variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 2048 # 2 vCPU (vs 4 in prod)
}

variable "ecs_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 4096 # 4 GB (vs 8 in prod)
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1 # 1 task (vs 2 in prod)
}

variable "ecs_capacity_provider" {
  description = "ECS capacity provider (FARGATE or FARGATE_SPOT)"
  type        = string
  default     = "FARGATE_SPOT" # 70% cheaper
}

variable "container_port" {
  description = "Container port for the application"
  type        = number
  default     = 8002
}

variable "container_image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "preprod"
}

# -----------------------------------------------------------------------------
# Database Configuration (Serverless for cost savings)
# -----------------------------------------------------------------------------
variable "aurora_cluster_identifier" {
  description = "Aurora cluster identifier"
  type        = string
  default     = "binomial-sentry-cluster-preprod"
}

variable "aurora_min_capacity" {
  description = "Aurora Serverless v2 minimum ACU"
  type        = number
  default     = 0.5 # Scales down when idle
}

variable "aurora_max_capacity" {
  description = "Aurora Serverless v2 maximum ACU"
  type        = number
  default     = 2.0 # Caps compute
}

variable "db_master_username" {
  description = "Database master username (not used - managed by AWS Secrets Manager)"
  type        = string
  sensitive   = true
  default     = "" # Username managed by AWS Secrets Manager
}

variable "db_master_password" {
  description = "Database master password (not used - managed by AWS Secrets Manager)"
  type        = string
  sensitive   = true
  default     = "" # Password managed by AWS Secrets Manager
}

# -----------------------------------------------------------------------------
# ALB Configuration
# -----------------------------------------------------------------------------
variable "alb_name" {
  description = "Application Load Balancer name"
  type        = string
  default     = "binomial-sentry-alb-preprod"
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (wildcard or preprod-specific)"
  type        = string
}

# -----------------------------------------------------------------------------
# Domain Configuration
# -----------------------------------------------------------------------------
variable "domain_name" {
  description = "Subdomain for pre-production backend API"
  type        = string
  default     = "api-preprod.binomialsentry.ai"
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID (shared with production)"
  type        = string
}

# -----------------------------------------------------------------------------
# EFS Configuration
# -----------------------------------------------------------------------------
variable "efs_file_system_id" {
  description = "EFS file system ID (shared with production)"
  type        = string
}

variable "efs_security_group_id" {
  description = "EFS security group ID (shared with production mount targets)"
  type        = string
}

variable "efs_access_point_path" {
  description = "EFS access point root path for preprod"
  type        = string
  default     = "/preprod"
}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7 # Shorter retention (vs 30 in prod)
}

# -----------------------------------------------------------------------------
# Frontend Configuration
# -----------------------------------------------------------------------------
variable "frontend_domain_name" {
  description = "Domain name for frontend"
  type        = string
  default     = "preprod.binomialsentry.ai"
}
