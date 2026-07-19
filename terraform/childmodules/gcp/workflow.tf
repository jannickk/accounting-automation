


# Create a dedicated service account
resource "google_service_account" "workflows_service_account" {
  project      = var.project_id
  account_id   = "account-auto-workflow-sa"
  display_name = "A service account under which the workflow for accounting automation runs"
}

## Grant the the service account the required permissions to run the workflow 
## in the project
resource "google_project_iam_member" "workflows_service_account" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

# Force creation of the Workflows service agent
resource "google_project_service_identity" "workflows" {
  provider = google-beta
  project  = var.project_id
  service  = "workflows.googleapis.com"
}

# Create a workflow
resource "google_workflows_workflow" "default" {
  project     = var.project_id
  depends_on  = [google_project_service.services, google_project_service_identity.workflows]
  name        = "accounting-automation"
  region      = var.region
  description = "Accounting automation workflow"
  # The identity under which the workflow runs
  service_account = google_service_account.workflows_service_account.id

  deletion_protection = false # set to "true" in production

  labels = {
    env = "test"
  }
  user_env_vars = {
    url = "https://timeapi.io/api/Time/current/zone?timeZone=Europe/Amsterdam"
  }
  source_contents = <<-EOF
  - getCurrentDate:
      call: http.get
      args:
          url: $${sys.get_env("url")}
      result: currentDate
  - readWikipedia:
      call: http.get
      args:
          url: https://en.wikipedia.org/w/api.php
          query:
              action: opensearch
              search: $${currentDate.body.dayOfWeek}
      result: wikiResult
  - returnOutput:
      return: $${wikiResult.body[1]}

  - run_job:
      call: http.post
      args:
          url: https://run.googleapis.com/v1/projects/my-project/locations/europe-west1/jobs/my-batch-job:run
          auth:
            type: OAuth2
      result: run_response

  - return_execution:
      return: $${run_response.body}
EOF


}
