output "resource_group_name" {
  description = "Name of the Azure resource group"
  value       = azurerm_resource_group.accounting_automation.name
}

output "resource_group_id" {
  description = "ID of the Azure resource group"
  value       = azurerm_resource_group.accounting_automation.id
}

output "container_app_environment_id" {
  description = "Container Apps Environment ID"
  value       = azurerm_container_app_environment.container_apps_env.id
}

output "container_app_environment_name" {
  description = "Container Apps Environment name"
  value       = azurerm_container_app_environment.container_apps_env.name
}

output "container_app_environment_default_domain" {
  description = "Default domain for Container Apps"
  value       = azurerm_container_app_environment.container_apps_env.default_domain
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for monitoring"
  value       = azurerm_log_analytics_workspace.container_apps_logs.id
}

output "user_assigned_identity_id" {
  description = "User assigned identity ID for container apps"
  value       = azurerm_user_assigned_identity.container_apps_identity.id
}

output "user_assigned_identity_client_id" {
  description = "Client ID of the user assigned identity"
  value       = azurerm_user_assigned_identity.container_apps_identity.client_id
}

output "user_assigned_identity_principal_id" {
  description = "Principal ID of the user assigned identity"
  value       = azurerm_user_assigned_identity.container_apps_identity.principal_id
}

output "container_registry_id" {
  description = "Container Registry ID"
  value       = azurerm_container_registry.acr.id
}

output "container_registry_name" {
  description = "Container Registry name"
  value       = azurerm_container_registry.acr.name
}

output "container_registry_login_server" {
  description = "Container Registry login server URL"
  value       = azurerm_container_registry.acr.login_server
}

output "container_registry_admin_username" {
  description = "Container Registry admin username"
  value       = azurerm_container_registry.acr.admin_username
}

output "container_registry_admin_password" {
  description = "Container Registry admin password (sensitive)"
  value       = azurerm_container_registry.acr.admin_password
  sensitive   = true
}

output "vnet_id" {
  description = "Virtual network ID"
  value       = azurerm_virtual_network.vnet.id
}

output "aks_subnet_id" {
  description = "AKS subnet ID"
  value       = azurerm_subnet.aks_subnet.id
}

output "user_assigned_identity_id" {
  description = "User assigned identity ID for AKS"
  value       = azurerm_user_assigned_identity.aks_identity.id
}

output "user_assigned_identity_client_id" {
  description = "Client ID of the user assigned identity"
  value       = azurerm_user_assigned_identity.aks_identity.client_id
}

output "user_assigned_identity_principal_id" {
  description = "Principal ID of the user assigned identity"
  value       = azurerm_user_assigned_identity.aks_identity.principal_id
}
