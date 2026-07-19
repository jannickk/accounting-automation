

resource "google_service_account" "service_account_accounting_automation" {
  account_id   = "accounting-automation"
  display_name = "Service Account to Authenticate against project resources"
  project = "${var.project_id}"
}