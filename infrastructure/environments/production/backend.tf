# =============================================================================
# Production Backend Configuration
# =============================================================================
# Remote state stored in S3 with DynamoDB locking

terraform {
  backend "s3" {
    bucket         = "binomial-sentry-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "binomial-sentry-terraform-locks"
  }
}
