# Archetype "container-postgres" (ADR-024). The only stack CloudPilot applies today.
# Values come from the deployment (cloudpilot.auto.tfvars.json); nothing here is generated
# by a language model, and nothing comes from the analyzed repository except the port,
# health path and variable names the architect recorded.

terraform {
  required_version = "~> 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "= 3.9.1"
    }
  }

  # bucket, key, region and use_lockfile are passed at init (ADR-027)
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = merge(var.tags, {
      "cloudpilot:deployment-id" = var.deployment_id
      "cloudpilot:managed-by"    = "cloudpilot"
    })
  }
}
