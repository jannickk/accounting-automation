

terraform {

    required_providers {

        azurerm = {
            source = "hashicorp/azurerm"
            version = "~> 4.0"

        }

    }

}


// The provider is configured via the Environment

provider "azurerm" {
  features {
    kubernetes_cluster {
      run_command_enabled = true
    }
  }
}
