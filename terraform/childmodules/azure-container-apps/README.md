# Azure Container Service Module

This Terraform module provisions Azure Container Apps and Azure Container Registry (ACR) for the accounting automation system.

## Resources Provisioned

### Core Infrastructure
- **Azure Resource Group** - Container for all Azure resources
- **Azure Container Apps Environment** - Serverless container hosting environment
- **Azure Container Registry (ACR)** - Private container registry
- **Container Apps Environment** - Public environment without VNet integration
- **Network Security Group** - Ingress/egress rules for public container apps
- **Log Analytics Workspace** - Monitoring and logging
- **User Assigned Identity** - Service identity for container apps

## Resources NOT Included
This module uses **Azure Container Apps** (serverless) instead of Azure Kubernetes Service (AKS):
- ✅ Simplified container deployment
- ✅ No cluster management required
- ✅ Auto-scaling out of the box
- ✅ Lower operational overhead
- ✅ Pay-per-use pricing

## Variables

### Required (must be provided at runtime)
- `azure_subscription_id` - Azure subscription ID
- `azure_client_id` - Service principal client ID
- `azure_client_secret` - Service principal secret
- `azure_tenant_id` - Azure tenant ID

### Optional (with sensible defaults)
- `region` - Azure region (default: "westeurope")
- `container_apps_cpu` - CPU allocation (default: "0.5")
- `container_apps_memory` - Memory allocation in Gi (default: "1.0Gi")
- `container_apps_replicas` - Initial replicas (default: 1)
- `container_apps_max_replicas` - Max replicas for autoscaling (default: 5)
- `container_apps_min_replicas` - Min replicas for autoscaling (default: 1)
- `container_registry_sku` - ACR SKU tier (default: "Standard")
- `acr_admin_enabled` - Enable ACR admin user (default: true)
- `environment` - Environment name (default: "default")
- `tags` - Common tags for resources

## Usage

### 1. Set up Azure Service Principal

```bash
# Create service principal
az ad sp create-for-rbac --name "terraform-accounting-automation" \
  --role "Contributor" \
  --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID"

# Output will include:
# - appId (client_id)
# - password (client_secret)
# - tenant (tenant_id)
```

### 2. Create terraform.tfvars

```hcl
# terraform.tfvars in rootmodules/

# GCP variables
project_id   = "your-gcp-project"
region       = "us-central1"
project_name = "accounting-automation"
db_password  = "your-secure-password"

# Azure variables
azure_subscription_id = "your-azure-subscription-id"
azure_client_id       = "your-service-principal-client-id"
azure_client_secret   = "your-service-principal-secret"
azure_tenant_id       = "your-azure-tenant-id"
```

### 3. Initialize and Apply

```bash
cd terraform/rootmodules

terraform init
terraform plan
terraform apply
```

## Key Features

### Azure Container Apps Environment
- **Serverless**: No infrastructure to manage
- **Auto-scaling**: Scales from 1-5 replicas based on demand
- **Public environment**: No dedicated VNet required
- **Built-in monitoring**: Log Analytics integration
- **ACR integration**: Seamless pull from private registry

### Azure Container Registry
- **Private**: Secured by default
- **Admin account**: Optional admin user for push/pull
- **Service endpoints**: Direct access from VNet

### Networking
- **Public Container Apps environment**: No dedicated VNet required
- **Service Endpoints**: Not required for public access
- **NSG Rules**: HTTP/HTTPS inbound, all outbound allowed

## Deploying Containers

### Get Container Registry Details

```bash
# Set Azure subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Get ACR login server
az acr show --resource-group "rg-accounting-automation-westeurope" \
  --name "acraccountingautomationwesteurope" \
  --query loginServer -o tsv
```

### Push Images to ACR

```bash
# Login to ACR
az acr login --name "acraccountingautomationwesteurope"

# Tag image
docker tag myapp:latest acraccountingautomationwesteurope.azurecr.io/myapp:latest

# Push image
docker push acraccountingautomationwesteurope.azurecr.io/myapp:latest
```

### Create Container App

```bash
# Example: Deploy a container app
az containerapp create \
  --name "app-accounting" \
  --resource-group "rg-accounting-automation-westeurope" \
  --environment "cae-accounting-automation-westeurope" \
  --image "acraccountingautomationwesteurope.azurecr.io/myapp:latest" \
  --registry-server "acraccountingautomationwesteurope.azurecr.io" \
  --registry-identity "system" \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 5
```

## Outputs

The module exports the following values:

- `container_app_environment_name` - Name of Container Apps environment
- `container_app_environment_id` - Environment ID
- `container_app_environment_default_domain` - Default domain for apps
- `container_registry_name` - Name of ACR
- `container_registry_login_server` - ACR login server URL
- `log_analytics_workspace_id` - Log Analytics workspace ID
- `resource_group_name` - Resource group name

Access outputs:
```bash
terraform output container_app_environment_name
terraform output -json container_registry_login_server
```

## Security Considerations

1. **Service Principal**: Use Managed Identity credentials in production
2. **ACR Admin**: Keep admin user disabled in production, use RBAC roles
3. **Network Policies**: VNet integration provides network isolation
4. **Secrets**: Use Key Vault for container app secrets/environment variables
5. **Registry Access**: Container apps use system-assigned identity for ACR pull

## Cost Optimization

- **CPU/Memory**: Start with 0.25 CPU / 0.5 Gi memory for development
- **Replicas**: Set min_replicas to 0 for dev environments (scales to 0)
- **ACR SKU**: Use "Basic" for private registries without replication
- **Container Apps**: Pay only for running containers, no additional infrastructure cost

## Monitoring

### View Container App Logs

```bash
# Stream logs
az containerapp logs show \
  --name "app-accounting" \
  --resource-group "rg-accounting-automation-westeurope" \
  --follow

# Query Log Analytics
az monitor log-analytics query \
  --workspace "/subscriptions/YOUR_SUBSCRIPTION_ID/resourcegroups/rg-accounting-automation-westeurope/providers/microsoft.operationalinsights/workspaces/law-containerapps-accounting-automation"
```

### View Metrics

```bash
# Container app metrics
az containerapp show \
  --name "app-accounting" \
  --resource-group "rg-accounting-automation-westeurope" \
  --query properties.template
```

## Troubleshooting

### Container won't start
- Check image exists in ACR: `az acr repository list --name acraccountingautomationwesteurope`
- Check image pull identity: Verify system/user identity has AcrPull role
- Check memory/CPU: Ensure allocation is sufficient for app

### Can't push to ACR
- Verify authentication: `az acr login --name acraccountingautomationwesteurope`
- Check quota limits: Registry SKU may limit push operations
- Verify service principal permissions: Should have AcrPush role

### High latency
- Check replica scaling: `az containerapp show --name APP --resource-group RG`
- Monitor CPU/memory usage in Log Analytics
- Review application logs for performance issues

## Next Steps

1. Deploy application containers using `az containerapp create`
2. Set up GitHub/Docker Hub integrations for CI/CD
3. Configure custom domains and TLS certificates
4. Implement Azure Key Vault for secrets management
5. Set up traffic splitting for blue/green deployments
