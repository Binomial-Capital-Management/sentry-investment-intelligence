# =============================================================================
# Bootstrap Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region for state management resources"
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  type        = string
  default     = "binomial-sentry-terraform-state"
}

variable "lock_table_name" {
  description = "Name of the DynamoDB table for state locking"
  type        = string
  default     = "binomial-sentry-terraform-locks"
}
