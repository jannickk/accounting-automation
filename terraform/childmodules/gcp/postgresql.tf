resource "google_sql_database_instance" "main" {
  name             = "postgresql-instance"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.project_id

  settings {
    tier              = "db-f1-micro"
    disk_type         = "PD_HDD"
    disk_size         = 10
    availability_type = "ZONAL"
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled = true
    }
  }

  deletion_protection = true # Set to true for production
}

resource "google_sql_database" "database" {
  name     = "accounting-db"
  instance = google_sql_database_instance.main.name
  project  = var.project_id
}

resource "google_sql_user" "users" {
  name     = "postgres-user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
  project  = var.project_id
}
