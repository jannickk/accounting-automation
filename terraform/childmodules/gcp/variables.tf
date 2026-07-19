



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
  description = "The project name"
}

variable "db_password" {
  description = "The password for the default database user"
  type        = string
  sensitive   = true
}
