# =============================================================================
# Pre-Production Environment Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------
output "vpc_id" {
  description = "VPC ID (shared with production)"
  value       = data.aws_vpc.main.id
}

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------
output "alb_security_group_id" {
  description = "ALB security group ID"
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "ECS tasks security group ID"
  value       = aws_security_group.ecs.id
}

output "rds_security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "Redis security group ID"
  value       = aws_security_group.redis.id
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

# -----------------------------------------------------------------------------
# Load Balancer
# -----------------------------------------------------------------------------
output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.main.arn
}

output "target_group_arn" {
  description = "Target group ARN"
  value       = aws_lb_target_group.main.arn
}

# -----------------------------------------------------------------------------
# ECS
# -----------------------------------------------------------------------------
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.main.name
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
output "aurora_cluster_endpoint" {
  description = "Aurora cluster endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora reader endpoint"
  value       = aws_rds_cluster.main.reader_endpoint
}

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------
output "efs_access_point_id" {
  description = "EFS access point ID for preprod"
  value       = aws_efs_access_point.preprod.id
}

# -----------------------------------------------------------------------------
# DNS
# -----------------------------------------------------------------------------
output "preprod_url" {
  description = "Pre-production URL"
  value       = "https://${var.domain_name}"
}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
output "ecs_log_group_name" {
  description = "ECS CloudWatch log group name"
  value       = aws_cloudwatch_log_group.ecs.name
}

# -----------------------------------------------------------------------------
# Cost Estimates
# -----------------------------------------------------------------------------
output "estimated_monthly_cost" {
  description = "Estimated monthly cost breakdown"
  value       = <<-EOT
    Estimated Pre-Production Monthly Costs:
    - ECS Fargate Spot (1 × 2 vCPU / 4 GB): ~$15
    - Aurora Serverless v2 (0.5-2 ACU):    ~$30-50
    - Application Load Balancer:            ~$20
    - ElastiCache Redis (t4g.micro):        ~$12
    - CloudWatch Logs (7-day retention):    ~$5
    - EFS Access Point:                     ~$1
    ----------------------------------------
    Total Estimate:                         ~$85-105/month
  EOT
}
