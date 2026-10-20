# =============================================================================
# Production Environment - Binomial Sentry
# =============================================================================
# This configuration manages all production infrastructure.
# Resources are imported from existing AWS infrastructure.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

# Reference existing VPC (will be imported)
data "aws_vpc" "main" {
  id = var.vpc_id
}

# Reference availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# -----------------------------------------------------------------------------
# VPC (Imported)
# -----------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Internet Gateway (Imported)
# -----------------------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# -----------------------------------------------------------------------------
# Subnets (Imported)
# -----------------------------------------------------------------------------

# Private Subnet - AZ 1a (ECS/EFS)
resource "aws_subnet" "private_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project_name}-private-1a"
    Type = "private"
  }
}

# Public Subnet - AZ 1b (ALB)
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-1b"
    Type = "public"
  }
}

# Private Subnet - AZ 1a (DB)
resource "aws_subnet" "private_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.3.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project_name}-private-1a-db"
    Type = "private"
  }
}

# Public Subnet - AZ 1a (NAT)
resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.4.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-1a"
    Type = "public"
  }
}

# -----------------------------------------------------------------------------
# NAT Gateway (Imported)
# -----------------------------------------------------------------------------
resource "aws_eip" "nat" {
  domain = "vpc"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.private_1.id

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.project_name}-nat-gateway"
  }

  depends_on = [aws_internet_gateway.main]
}

# -----------------------------------------------------------------------------
# Route Tables (Imported)
# -----------------------------------------------------------------------------

# Private route table - routes through NAT Gateway
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "binomial-sentry-private-routes"
  }
}

# Public route table - routes through Internet Gateway
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "binomial-sentry-public-routes"
  }
}

# Route table associations
# NOTE: Only private_2 has an explicit association in AWS.
# Other subnets use the VPC main route table (no explicit association).
resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# -----------------------------------------------------------------------------
# VPC Endpoint for S3 (Imported)
# -----------------------------------------------------------------------------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.us-east-1.s3"
  vpc_endpoint_type = "Gateway"
  # Include all route tables that currently use this endpoint
  route_table_ids = [
    aws_route_table.private.id, # rtb-06ec01c6b64611d56 (private routes)
    aws_route_table.public.id,  # rtb-0711c7019f28ffd7c (public routes)
    "rtb-0c6ac4102a6210a56",    # VPC main route table
    "rtb-0492364679f8c230e",    # binomial-nat-gateway-rt (used by private_1, public_1, public_2)
  ]

  tags = {
    Name = "binomial-sentry-s3-endpoint"
  }
}

# -----------------------------------------------------------------------------
# Security Groups (Imported)
# -----------------------------------------------------------------------------

# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "sentry-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sentry-alb-sg"
  }
}

# ECS Tasks Security Group
resource "aws_security_group" "ecs" {
  name        = "binomial-ecs-tasks-sg"
  description = "ECS Tasks security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "ALB to ECS"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "binomial-ecs-tasks-sg"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name        = "sentry-db-sg"
  description = "Created by RDS management console"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "From ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    description = "Self-reference"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sentry-db-sg"
  }
}

# EFS Security Group
resource "aws_security_group" "efs" {
  name        = "sentry-efs-sg"
  description = "Allow NFS access from ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from ECS"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    description     = "NFS from preprod ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = ["<SECURITY_GROUP_ID>"] # preprod ECS SG
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sentry-efs-sg"
  }
}

# -----------------------------------------------------------------------------
# ElastiCache Redis (Imported)
# -----------------------------------------------------------------------------
# NOTE: Production Redis currently uses the VPC default security group.
# This is not ideal but we import as-is. Consider migrating to a dedicated SG.

# Reference the VPC default security group (used by Redis)
# We reference it as data to avoid managing the shared default SG
data "aws_security_group" "default" {
  vpc_id = aws_vpc.main.id
  name   = "default"
}

# Redis Subnet Group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "binomial-sentry-redis-cache"
  subnet_ids = [aws_subnet.public_2.id, aws_subnet.private_2.id]

  tags = {
    Name = "binomial-sentry-redis-cache"
  }
}

# Redis Replication Group
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "binomial-redis"
  description          = "Easy created demo cluster on 2025-09-24T10:28:18.715Z"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = "cache.t4g.micro"
  port           = 6379

  # Cluster mode enabled with single shard
  num_node_groups         = 1
  replicas_per_node_group = 0
  parameter_group_name    = "default.redis7.cluster.on"

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [data.aws_security_group.default.id]

  # Encryption settings
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"

  # No auth token (relies on security group)
  auth_token = null

  # Failover settings
  automatic_failover_enabled = true
  multi_az_enabled           = false

  # Maintenance
  maintenance_window         = "sun:05:00-sun:06:00"
  snapshot_retention_limit   = 0
  auto_minor_version_upgrade = true

  apply_immediately = false

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "binomial-redis"
  }
}

# -----------------------------------------------------------------------------
# S3 Buckets (Imported)
# -----------------------------------------------------------------------------

# Frontend bucket
resource "aws_s3_bucket" "frontend" {
  bucket = var.frontend_bucket_name

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Frontend Assets"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Artifacts bucket
resource "aws_s3_bucket" "artifacts" {
  bucket = var.artifacts_bucket_name

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Production Artifacts"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# EFS (Imported)
# -----------------------------------------------------------------------------
resource "aws_efs_file_system" "main" {
  performance_mode = "generalPurpose"
  encrypted        = true
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "binomial-sentry-efs"
  }
}

resource "aws_efs_access_point" "main" {
  file_system_id = aws_efs_file_system.main.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/data"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0755"
    }
  }

  tags = {
    Name = "binomial-sentry-data"
  }
}

# -----------------------------------------------------------------------------
# EFS Mount Targets (Imported)
# -----------------------------------------------------------------------------
# EFS requires one mount target per AZ for high availability.
# These exist in us-east-1a (private) and us-east-1b (public).

resource "aws_efs_mount_target" "private_1a" {
  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = aws_subnet.private_1.id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_mount_target" "public_1b" {
  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = aws_subnet.public_1.id
  security_groups = [aws_security_group.efs.id]
}

# -----------------------------------------------------------------------------
# ECR Repository (Imported)
# -----------------------------------------------------------------------------
resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false # Matches current AWS config
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Backend Container Repository"
  }
}

# -----------------------------------------------------------------------------
# ECS Cluster (Imported)
# -----------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = var.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "enhanced"
  }

  configuration {
    execute_command_configuration {
      logging = "DEFAULT"
    }
  }

  tags = {
    Name = var.ecs_cluster_name
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group (Imported)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = 0 # Never expire (matches current AWS config)

  tags = {
    Name = "ECS Backend Logs"
  }
}

# -----------------------------------------------------------------------------
# Route53 Zone (Imported)
# -----------------------------------------------------------------------------
# NOTE: Public DNS is managed by Cloudflare, not Route53.
# This zone exists but is not actively used for public resolution.
# Private hosted zone was deleted to fix DNS resolution issues in VPC.
# -----------------------------------------------------------------------------
resource "aws_route53_zone" "main" {
  name    = var.domain_name
  comment = "Domain name hosting"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Primary Domain Zone"
  }
}

# -----------------------------------------------------------------------------
# Day 3: Application Load Balancer (Imported)
# -----------------------------------------------------------------------------
resource "aws_lb" "main" {
  name               = var.alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name = var.alb_name
  }
}

resource "aws_lb_target_group" "main" {
  name        = "binomial-sentry-backend-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 5
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name = "binomial-sentry-backend-tg"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# -----------------------------------------------------------------------------
# Day 3: CloudFront Distribution (Imported) - Updated to match live config
# -----------------------------------------------------------------------------

# Managed Cache Policies (AWS-provided)
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

# Custom Origin Request Policies
# IMPORTANT: These custom policies include Last-Event-ID header for SSE streaming
# Do NOT replace with managed policies - they will break SSE resumption!
data "aws_cloudfront_origin_request_policy" "cors_s3" {
  # Using custom policy "Custom-SSE-CORS-Policy" that includes Last-Event-ID header
  id = "bf8e1e37-ceeb-413b-ae66-220f26ed3892"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

# Custom Response Headers Policy
# IMPORTANT: This policy allows credentials with specific origins (not wildcard)
# Do NOT replace with managed policies - they will break authenticated requests!
data "aws_cloudfront_response_headers_policy" "cors_preflight" {
  # Using custom policy "Custom-SSE-CORS-Headers" that allows credentials
  id = "b9342cf0-7c1b-4f62-9e62-e189b6c74690"
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2"
  comment             = "Binomial Sentry Frontend"
  default_root_object = "index.html"
  aliases             = [var.domain_name]
  price_class         = "PriceClass_All"

  # Origin 1: S3 Frontend (static assets)
  origin {
    domain_name = "${var.frontend_bucket_name}.s3.${var.aws_region}.amazonaws.com"
    origin_id   = "${var.frontend_bucket_name}.s3.${var.aws_region}.amazonaws.com-mfta9uxgmdf"

    # Note: Live config has no OAC - bucket uses public access or legacy OAI
    # If you want to add OAC for security, uncomment below and update S3 policy
    # origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Origin 2: Backend ALB (API requests)
  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "binomial-sentry-backend-alb"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  # Default behavior: Serve frontend from S3
  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "${var.frontend_bucket_name}.s3.${var.aws_region}.amazonaws.com-mfta9uxgmdf"
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.cors_s3.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.cors_preflight.id
  }

  # /api/* behavior: Route to backend ALB (no caching)
  ordered_cache_behavior {
    path_pattern             = "/api/*"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "binomial-sentry-backend-alb"
    viewer_protocol_policy   = "redirect-to-https"
    compress                 = true
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
  }

  # SPA routing: Return index.html for 403/404 errors
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "binomial-sentry-cdn"
  }
}

# -----------------------------------------------------------------------------
# Day 3: Lambda Functions (Imported)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Lambda Functions (NOT managed by Terraform)
# -----------------------------------------------------------------------------
# Lambda functions are deployed via their own CI/CD pipeline in lambdas/
# They use AWS-managed S3 for code storage which can't be imported to Terraform.
# Functions: earnings-ipo-calendar, fear-greed-index
#
# Data source for reference if needed:
data "aws_iam_role" "lambda_role" {
  name = "earnings-ipo-lambda-role"
}

# -----------------------------------------------------------------------------
# Day 4: Aurora PostgreSQL Cluster (Imported)
# -----------------------------------------------------------------------------

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name = "default-<VPC_ID>"
  subnet_ids = [
    aws_subnet.private_1.id, # us-east-1a
    aws_subnet.public_1.id,  # us-east-1b
    aws_subnet.private_2.id, # us-east-1a
    aws_subnet.public_2.id,  # us-east-1a
  ]

  tags = {
    Name = "Aurora DB Subnet Group"
  }
}

# Aurora Cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier = var.aurora_cluster_identifier
  engine             = "aurora-postgresql"
  engine_version     = "16.8"
  database_name      = "sentry_db"
  master_username    = var.db_master_username
  port               = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Snapshots
  skip_final_snapshot   = true
  copy_tags_to_snapshot = true
  deletion_protection   = true

  # Performance Insights
  performance_insights_enabled = true

  # IMPORTANT: manage_master_user_password is true in AWS (uses Secrets Manager)
  manage_master_user_password = true

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      master_password,
      master_username, # Already set, cannot change
    ]
  }

  tags = {
    Name = var.aurora_cluster_identifier
  }
}

# Aurora Instance 1 (Primary)
resource "aws_rds_cluster_instance" "instance_1" {
  identifier         = "binomial-sentry-cluster-instance-1"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.aurora_instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = "arn:aws:iam::<AWS_ACCOUNT_ID>:role/rds-monitoring-role"

  # Performance Insights
  performance_insights_enabled = true

  promotion_tier = 1

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name                = "binomial-sentry-cluster-instance-1"
    devops-guru-default = "binomial-sentry-cluster"
  }
}

# Aurora Instance 2 (Replica)
resource "aws_rds_cluster_instance" "instance_2" {
  identifier         = "binomial-sentry-cluster-instance-1-us-east-1a"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.aurora_instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = "arn:aws:iam::<AWS_ACCOUNT_ID>:role/rds-monitoring-role"

  # Performance Insights
  performance_insights_enabled = true

  promotion_tier = 1

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name                = "binomial-sentry-cluster-instance-1-us-east-1a"
    devops-guru-default = "binomial-sentry-cluster"
  }
}

# -----------------------------------------------------------------------------
# Day 4: ECS Service (Imported)
# -----------------------------------------------------------------------------

# Reference existing task definition (managed by CI/CD)
data "aws_ecs_task_definition" "main" {
  task_definition = "binomial-sentry-backend"
}

resource "aws_ecs_service" "main" {
  name            = "binomial-sentry-backend-service-b9ze202w"
  cluster         = aws_ecs_cluster.main.id
  task_definition = data.aws_ecs_task_definition.main.arn
  desired_count   = var.ecs_desired_count

  # Enable ECS exec for debugging and migrations
  enable_execute_command = true

  # Uses capacity provider strategy, NOT launch_type
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 0
  }

  network_configuration {
    subnets          = [aws_subnet.private_1.id, aws_subnet.public_1.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = "binomial-sentry-backend"
    container_port   = var.container_port
  }

  # CRITICAL: Allow CI/CD to manage task definition independently
  lifecycle {
    ignore_changes = [
      task_definition,
      desired_count,
    ]
  }

  tags = {
    Name = "binomial-sentry-backend-service"
  }
}

# -----------------------------------------------------------------------------
# GitHub Actions OIDC Authentication
# -----------------------------------------------------------------------------
# OIDC federation eliminates long-lived IAM access keys in GitHub Actions.
# Workflows authenticate by assuming IAM roles with short-lived credentials.

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "github-actions-oidc"
  }
}

# Deploy role — used by backend/frontend deploy workflows (main branch only)
resource "aws_iam_role" "github_actions_deploy" {
  name        = "github-actions-deploy"
  description = "GitHub Actions deploy role for CI/CD pipelines (OIDC)"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:Binomial-Capital-Management/binomialai:ref:refs/heads/main"
        }
      }
    }]
  })

  tags = {
    Name = "github-actions-deploy"
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "DeployPolicy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = aws_ecr_repository.backend.arn
      },
      {
        Sid    = "ECS"
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DeregisterTaskDefinition",
          "ecs:ListTaskDefinitions",
          "ecs:DescribeTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "ecs:ListTasks"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3Frontend"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:PutBucketWebsite",
          "s3:GetBucketWebsite",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.frontend.arn,
          "${aws_s3_bucket.frontend.arn}/*",
          "arn:aws:s3:::binomial-sentry-frontend-preprod",
          "arn:aws:s3:::binomial-sentry-frontend-preprod/*"
        ]
      },
      {
        Sid    = "CloudFront"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",
          "cloudfront:GetInvalidation",
          "cloudfront:GetDistribution",
          "cloudfront:UpdateDistribution"
        ]
        Resource = "*"
      },
      {
        Sid    = "PassRole"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          "arn:aws:iam::<AWS_ACCOUNT_ID>:role/ecsTaskExecutionRole",
          "arn:aws:iam::<AWS_ACCOUNT_ID>:role/ecsTaskRole"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      }
    ]
  })
}

# Terraform role — used by infrastructure workflows (all branches for plan)
resource "aws_iam_role" "github_actions_terraform" {
  name        = "github-actions-terraform"
  description = "GitHub Actions Terraform role for infrastructure management (OIDC)"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:Binomial-Capital-Management/binomialai:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Name = "github-actions-terraform"
  }
}

resource "aws_iam_role_policy_attachment" "github_actions_terraform" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
