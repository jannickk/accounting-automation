module "accounting_automation" {
  source       = "../childmodules"
  project_id   = var.project_id
  region       = var.region
  project_name = var.project_name
  db_password  = var.db_password
}

module "azure_container_service" {
  source = "../childmodules/azure-container-service"

  project_id   = var.project_id
  region       = var.region
  project_name = var.project_name
  db_password  = var.db_password

  # Azure-specific variables
  azure_subscription_id = var.azure_subscription_id
  azure_client_id       = var.azure_client_id
  azure_client_secret   = var.azure_client_secret
  azure_tenant_id       = var.azure_tenant_id

  # Container Apps configuration
  container_apps_cpu         = "0.5"
  container_apps_memory      = "1.0Gi"
  container_apps_replicas    = 1
  container_apps_max_replicas = 5
  container_apps_min_replicas = 1
  container_registry_sku      = "Standard"

  tags = {
    env = "default"
  }
}

