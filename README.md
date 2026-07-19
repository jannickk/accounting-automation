## The accountinf infrastructure is created in Google CLoud


## For the automation to work we must first manually configure the Workload Identity Federation so that Gitlab CI can authenticate against Google


1) Create a Workload Identity Pool

gcloud iam workload-identity-pools create gitlab-pool --location=global --display-name="GitLab Pool"

2) Inside that pool create a workload Identity provider

gcloud iam workload-identity-pools providers create-oidc gitlab-provider \
  --location=global \
  --workload-identity-pool=gitlab-pool \
  --display-name="GitLab Provider" \
  --issuer-uri="https://gitlab.com"

3) Create a User managed service account

4) Create a iam-policy binding to bind the service account to the workload identity user 

gcloud iam service-accounts add-iam-policy-binding \
  <SERVICE ACCOUNT EMAIL>@<PROJECT_ID>.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/gitlab-pool/massflows/terraform-infrastructure"



######

1) All Emails are checked in an Outlook inbox

2) The attachment is retrieved and stored in a bronze data layer partitioned by date-month

3) The bronze to silver job submits each document to Mistral Document AI and extracts relevant information from the invoice

4) the extracted information is stored in a silver invoice table and documents are copied to a silver storage location partionied by supplier and 


