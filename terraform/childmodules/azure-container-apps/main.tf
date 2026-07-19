# Azure Resource Group
resource "azurerm_resource_group" "accounting_automation" {
  name     = "rg-${var.project_name}-${var.region}"
  location = var.region

  tags = merge(
    var.tags,
    {
      Name     = "accounting-automation"
      Purpose  = "Container deployment with Azure Container Apps"
    }
  )
}

# Azure Container Registry
resource "azurerm_container_registry" "acr" {
  name                = "acr${replace(var.project_name, "-", "")}${var.region}"
  resource_group_name = azurerm_resource_group.accounting_automation.name
  location            = azurerm_resource_group.accounting_automation.location

  sku           = var.container_registry_sku
  admin_enabled = var.acr_admin_enabled

  public_network_access_enabled = true

  tags = merge(
    var.tags,
    {
      Name = "accounting-automation-registry"
    }
  )
}

# Log Analytics Workspace for monitoring
resource "azurerm_log_analytics_workspace" "container_apps_logs" {
  name                = "law-containerapps-${var.project_name}"
  location            = azurerm_resource_group.accounting_automation.location
  resource_group_name = azurerm_resource_group.accounting_automation.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = merge(
    var.tags,
    {
      Name = "container-apps-logs"
    }
  )
}

# Container Apps Environment
resource "azurerm_container_app_environment" "container_apps_env" {
  name                       = "cae-${var.project_name}-${var.region}"
  location                   = azurerm_resource_group.accounting_automation.location
  resource_group_name        = azurerm_resource_group.accounting_automation.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.container_apps_logs.id
  internal_load_balancer_enabled = false

  tags = merge(
    var.tags,
    {
      Name    = "accounting-automation-environment"
      Purpose = "Container Apps environment"
    }
  )
}

# User Assigned Identity for Container Apps to pull from ACR
resource "azurerm_user_assigned_identity" "container_apps_identity" {
  resource_group_name = azurerm_resource_group.accounting_automation.name
  location            = azurerm_resource_group.accounting_automation.location
  name                = "id-containerapps-${var.project_name}"

  tags = var.tags
}

# Role assignment for Container Apps to pull from ACR
resource "azurerm_role_assignment" "container_apps_acr_pull" {
  scope              = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id       = azurerm_user_assigned_identity.container_apps_identity.principal_id
}
