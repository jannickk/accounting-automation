

resource "google_bigquery_dataset" "accounting" {
  project       = var.project_id
  dataset_id    = "accounting"
  friendly_name = "emails"
  description   = "This is a dataset for storing emails in the outlook inbox"
  location      = var.region

  labels = {
    env = "default"
  }

  access {
    role          = "roles/bigquery.dataOwner"
    user_by_email = "jannick.kappelmann@massflows.net"
  }
}

# Give the right to edit the dataset
resource "google_bigquery_dataset_iam_member" "editor" {

  dataset_id = google_bigquery_dataset.accounting.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.service_account_accounting_automation.email}"
}


## Give the right to execute queries

#the role roles/bigquery.jobUser includes:
#bigquery.jobs.create
#bigquery.jobs.get
#bigquery.jobs.list
#permissions

resource "google_project_iam_member" "bigquery_jobs_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.service_account_accounting_automation.email}"
}


resource "google_bigquery_table" "emails" {

  dataset_id = google_bigquery_dataset.accounting.dataset_id
  table_id   = "emails"
  project    = var.project_id


  deletion_protection = true

  labels = {
    env = "default"
  }

  schema = <<EOF
[

  {
    "name": "id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "subject",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "numOfAttachments",
    "type": "INTEGER",
    "mode": "NULLABLE"
  },
  {
    "name": "receivedDateTime",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "ingestDateTime",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "processedDateTime",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "hashID",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "sender",
    "type": "RECORD",
    "mode": "NULLABLE",
    "fields": [
      {
        "name": "emailAddress",
        "type": "RECORD",
        "mode": "NULLABLE",
        "fields": [
          {
            "name": "name",
            "type": "STRING",
            "mode": "NULLABLE"
          },
          {
            "name": "address",
            "type": "STRING",
            "mode": "NULLABLE"
          }
        ]
      }
    ]
  },
  {
    "name": "body",
    "type": "RECORD",
    "mode": "NULLABLE",
    "fields": [
      {
        "name": "contentType",
        "type": "STRING",
        "mode": "NULLABLE"
      },
      {
        "name": "contentBytes",
        "type": "STRING",
        "mode": "NULLABLE"
      }
    ]
  },
  {
    "name": "from",
    "type": "RECORD",
    "mode": "NULLABLE",
    "fields": [
      {
        "name": "emailAddress",
        "type": "RECORD",
        "mode": "NULLABLE",
        "fields": [
          {
            "name": "name",
            "type": "STRING",
            "mode": "NULLABLE"
          },
          {
            "name": "address",
            "type": "STRING",
            "mode": "NULLABLE"
          }
        ]
      }
    ]
  },
  {
    "name": "toRecipients",
    "type": "RECORD",
    "mode": "NULLABLE",
    "fields": [
      {
        "name": "emailAddress",
        "type": "RECORD",
        "mode": "NULLABLE",
        "fields": [
          {
            "name": "name",
            "type": "STRING",
            "mode": "NULLABLE"
          },
          {
            "name": "address",
            "type": "STRING",
            "mode": "NULLABLE"
          }
        ]
      }
    ]
  }
]
EOF

}

resource "google_bigquery_table" "documents" {

  dataset_id = google_bigquery_dataset.accounting.dataset_id
  table_id   = "documents"
  project    = var.project_id

  deletion_protection = true

  labels = {
    env = "default"
  }

  schema = <<EOF
[
  {
    "name": "emailID",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "fromEmailAddressName",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "isDuplicateOf",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "hashID",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "processedDocumentAI",
    "type": "BOOLEAN",
    "mode": "REQUIRED"
  },
  {
    "name": "processedDatetime",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "attachmentName",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "attachmentType",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "gcsUri",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "blobName",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "finalGcsUri",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "finalBlobName",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "uploadedToDatev",
    "type": "BOOLEAN",
    "mode": "REQUIRED"
  },
  {
    "name": "uploadedDatetime",
    "type": "STRING",
    "mode": "NULLABLE"
  }
]
EOF
}

resource "google_bigquery_table" "accounting_info" {

  dataset_id = google_bigquery_dataset.accounting.dataset_id
  table_id   = "accounting_info"
  project    = var.project_id

  deletion_protection = true

  labels = {
    env = "default"
  }

  schema = <<EOF
[
  {
    "name": "fromEmailAddressName",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "document_hash_id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "net_amount",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "net_amount_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_id",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_id_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "total_amount",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "total_amount_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_tax_id",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_tax_id_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "currency",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "currency_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_iban",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_iban_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_date",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_date_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_year",
    "type": "INT64",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_month",
    "type": "INT64",
    "mode": "NULLABLE"
  },
  {
    "name": "invoice_day",
    "type": "INT64",
    "mode": "NULLABLE"
  },
  {
    "name": "period_of_service_year",
    "type": "INT64",
    "mode": "NULLABLE"
  },
  {
    "name": "period_of_service_month",
    "type": "INT64",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_email",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_email_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_address",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_address_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_name",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_name_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_registration",
    "type": "STRING",
    "mode": "NULLABLE"
  },
  {
    "name": "supplier_registration_confidence",
    "type": "FLOAT",
    "mode": "NULLABLE"
  },
  {
    "name": "gcsUri",
    "type": "STRING",
    "mode": "NULLABLE"
  }
]
EOF
}