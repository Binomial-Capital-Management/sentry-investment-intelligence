# =============================================================================
# Pre-Production Backend Configuration
# =============================================================================
# Remote state stored in S3 with DynamoDB locking
# Uses separate state file from production

terraform {
  backend "s3" {
    bucket         = "binomial-sentry-terraform-state"
    key            = "preprod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "binomial-sentry-terraform-locks"
  }
}
