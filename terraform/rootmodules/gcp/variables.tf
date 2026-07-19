variable "project_id" {
  type        = string
  description = "Google project id"
}

variable "region" {
  type        = string
  description = "The region where the Google project resides"
}

variable "project_name" {
  type        = string
  description = "The name of the Google project"
}

variable "db_password" {
  type        = string
  description = "The password for the database user"
  sensitive   = true
}

