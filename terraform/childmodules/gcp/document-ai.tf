



resource "google_document_ai_processor" "processor" {

depends_on = [google_project_service.services]

  project      = var.project_id
  location     = "eu"
  display_name = "document-ai-${var.project_name}-${var.region}"
  type         = "INVOICE_PROCESSOR"
}


resource "google_document_ai_processor_default_version" "processor" {
  processor = google_document_ai_processor.processor.id
  version   = "${google_document_ai_processor.processor.id}/processorVersions/stable"

  lifecycle {
    ignore_changes = [
      # Using "stable" or "rc" will return a specific version from the API; suppressing the diff.
      version,
    ]
  }
}

## those roles are required to run the document ai processor and are granted on a project level
resource "google_project_iam_member" "document_ai_user" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.service_account_accounting_automation.email}"
}

resource "google_project_iam_member" "document_ai_viewer" {
  project = var.project_id
  role    = "roles/documentai.viewer"
  member  = "serviceAccount:${google_service_account.service_account_accounting_automation.email}"
}


