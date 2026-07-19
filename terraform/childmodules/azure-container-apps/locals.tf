locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Project     = var.project_name
      Region      = var.region
    }
  )

  container_app_env_name = "cae-${var.project_name}-${var.region}"
  acr_name               = "acr${replace(var.project_name, "-", "")}${var.region}"
  rg_name                = "rg-${var.project_name}-${var.region}"

  container_apps_max_replicas = var.container_apps_max_replicas
  container_apps_min_replicas = var.container_apps_min_replicas
}
