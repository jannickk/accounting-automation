## Appears fine


resource "google_storage_bucket" "bucket" {
  project       = var.project_id
  name          = "storagebucket-${var.project_name}-${var.region}"
  location      = var.region
  storage_class = "STANDARD"

  public_access_prevention = "enforced"

  hierarchical_namespace {
    enabled = true
  }

  uniform_bucket_level_access = true
}


resource "google_storage_bucket_iam_member" "admin" {

  bucket = google_storage_bucket.bucket.name
  role   = "roles/storage.admin"
  member = "user:jannick.kappelmann@massflows.net"

}

resource "google_storage_bucket_iam_member" "service_account" {
  bucket = google_storage_bucket.bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.service_account_accounting_automation.email}"
}
