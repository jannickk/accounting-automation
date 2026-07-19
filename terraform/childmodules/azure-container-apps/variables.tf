
variable "region" {
  type        = string
  description = "Azure region for resources"
  default     = "westeurope"
}

variable "project_name" {
  type        = string
  description = "Project name for resource naming"
}


variable "container_apps_cpu" {
  type        = string
  description = "CPU allocation for container apps"
  default     = "0.5"
}

variable "container_apps_memory" {
  type        = string
  description = "Memory allocation for container apps (in Gi)"
  default     = "1.0Gi"
}

variable "container_apps_replicas" {
  type        = number
  description = "Number of replicas for container apps"
  default     = 1
}

variable "container_apps_max_replicas" {
  type        = number
  description = "Maximum number of replicas for autoscaling"
  default     = 5
}

variable "container_apps_min_replicas" {
  type        = number
  description = "Minimum number of replicas for autoscaling"
  default     = 1
}

variable "container_registry_sku" {
  type        = string
  description = "SKU for Azure Container Registry"
  default     = "Standard"
}

variable "acr_admin_enabled" {
  type        = bool
  description = "Enable admin user for ACR"
  default     = true
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "default"
}

variable "tags" {
  type        = map(string)
  description = "Common tags for all resources"
  default = {
    environment = "default"
    managed_by  = "terraform"
  }
}
