

# resource "google_cloud_run_v2_job" "default" {
#   name     = "cloudrun-job"
#   location = "us-central1"
#   deletion_protection = false
#   template {
    
#     template{

#       volumes {
#         name = "cloudsql"
#         cloud_sql_instance {
#           instances = [google_sql_database_instance.instance.connection_name]
#         }
#       }

#       containers {
#         image = "us-docker.pkg.dev/cloudrun/container/job"

#         env {
#           name = "FOO"
#           value = "bar"
#         }

#         env {
#           name = "latestdclsecret"
#           value_source {
#             secret_key_ref {
#               secret = google_secret_manager_secret.secret.secret_id
#               version = "1"
#             }
#           }
#         }
#         volume_mounts {
#           name = "cloudsql"
#           mount_path = "/cloudsql"
#         }
#       }
#     }
#   }
# }


#   resource "google_cloud_run_v2_job_iam_member" "noauth" {
#     location = google_cloud_run_v2_service.default.location
#     name     = google_cloud_run_v2_service.default.name
#     role     = "roles/run.invoker"
#     member   = "allUsers"
#   }