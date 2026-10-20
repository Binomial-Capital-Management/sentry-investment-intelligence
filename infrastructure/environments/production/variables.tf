# =============================================================================
# Production Environment Variables
# =============================================================================

# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------
variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
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
# VPC & Networking
# -----------------------------------------------------------------------------
variable "vpc_id" {
  description = "Existing VPC ID to import"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# -----------------------------------------------------------------------------
# ECS Configuration
# -----------------------------------------------------------------------------
variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
  default     = "binomial-sentry-cluster"
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
  default     = "binomial-sentry-backend-service"
}

variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 4096 # 4 vCPU
}

variable "ecs_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 8192 # 8 GB
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "container_port" {
  description = "Container port for the application"
  type        = number
  default     = 8002
}

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------
variable "aurora_cluster_identifier" {
  description = "Aurora cluster identifier"
  type        = string
  default     = "binomial-sentry-cluster"
}

variable "aurora_instance_class" {
  description = "Aurora instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "aurora_instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 2
}

variable "db_master_username" {
  description = "Database master username"
  type        = string
  sensitive   = true
}

variable "db_master_password" {
  description = "Database master password (not used - managed by AWS Secrets Manager)"
  type        = string
  sensitive   = true
  default     = "" # Password managed by AWS Secrets Manager via manage_master_user_password = true
}

# -----------------------------------------------------------------------------
# ALB Configuration
# -----------------------------------------------------------------------------
variable "alb_name" {
  description = "Application Load Balancer name"
  type        = string
  default     = "binomial-sentry-backend-alb"
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

# -----------------------------------------------------------------------------
# Domain Configuration
# -----------------------------------------------------------------------------
variable "domain_name" {
  description = "Primary domain name"
  type        = string
  default     = "binomialsentry.ai"
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID"
  type        = string
}

# -----------------------------------------------------------------------------
# S3 Buckets
# -----------------------------------------------------------------------------
variable "frontend_bucket_name" {
  description = "S3 bucket for frontend assets"
  type        = string
  default     = "binomial-sentry-frontend-bcm001"
}

variable "artifacts_bucket_name" {
  description = "S3 bucket for artifacts"
  type        = string
  default     = "binomial-artifacts-prod"
}

# -----------------------------------------------------------------------------
# CloudFront
# -----------------------------------------------------------------------------
variable "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for frontend"
  type        = string
}

# -----------------------------------------------------------------------------
# EFS Configuration
# -----------------------------------------------------------------------------
variable "efs_file_system_id" {
  description = "EFS file system ID"
  type        = string
}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}
