terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # Remote state is intentionally not configured here. Configure a backend
  # (e.g. S3 + DynamoDB lock) per environment via `terraform init -backend-config`
  # so this module stays reusable. Never commit state files; see .gitignore.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}
