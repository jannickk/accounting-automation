

provider "google" {
  project = var.project_id
  region  = var.region
}

terraform {

  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.12"
    }
  }

  backend "gcs" {
    bucket = "terraform-common-prod-massflows"
    prefix = "accounting-automation"
  }



}
