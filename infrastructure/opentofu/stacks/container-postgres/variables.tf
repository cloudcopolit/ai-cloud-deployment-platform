variable "deployment_id" {
  type        = string
  description = "CloudPilot deployment id; tags every resource."
}

variable "name_prefix" {
  type        = string
  description = "Short prefix for AWS names (cp- plus 8 hex)."
  validation {
    condition     = can(regex("^cp-[0-9a-f]{8}$", var.name_prefix))
    error_message = "The name_prefix must look like cp-1a2b3c4d."
  }
}

variable "region" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "image" {
  type        = string
  description = "Container image pinned by digest (ADR-025)."
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "The image must be pinned by digest (ending in @sha256: and 64 hex)."
  }
}

variable "container_port" {
  type = number
}

variable "health_path" {
  type = string
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "ingress_cidrs" {
  type        = list(string)
  description = "Who may reach the load balancer (the owner's IP in the sandbox)."
  validation {
    condition     = length(var.ingress_cidrs) > 0 && alltrue([for c in var.ingress_cidrs : can(cidrnetmask(c)) && c != "0.0.0.0/0"])
    error_message = "The ingress_cidrs must be explicit CIDRs; 0.0.0.0/0 is not allowed."
  }
}

variable "environment" {
  type        = map(string)
  default     = {}
  description = "Extra plain environment variables (never secrets)."
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_engine_version" {
  type    = string
  default = "16"
}

variable "db_storage_gb" {
  type    = number
  default = 20
}

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "permissions_boundary_arn" {
  type        = string
  description = "Every role this stack creates carries the onboarding boundary (ADR-027)."
}
