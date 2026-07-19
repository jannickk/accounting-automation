from google.cloud.bigquery import Client as BigQueryClient
from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
from google.cloud import storage
from google.oauth2 import service_account
import asyncio
import os
import json
import logging
import base64
import aiohttp

logger = logging.getLogger(__name__)

# Initialize credentials
if os.environ.get("GCP_SERVICE_ACCOUNT_KEY"):
    service_account_info = json.loads(os.environ.get("GCP_SERVICE_ACCOUNT_KEY"))
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    project_id = service_account_info.get("project_id")
    bq_client = BigQueryClient(credentials=credentials, project=project_id)
else:
    credentials = None
    project_id = os.environ.get("GCP_PROJECT_ID")
    bq_client = BigQueryClient(project=project_id)


async def get_access_token():


    client_id = os.environ.get("O365_CLIENT_ID")
    client_secret = os.environ.get("O365_CLIENT_SECRET")
    tenant_id = os.environ.get("O365_TENANT_ID")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    async with aiohttp.ClientSession() as session:

        result = await session.post(

            authority + "/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }
        )
        if result.status != 200:
            print(f"Error acquiring token: {result.status}")
            return None

        else:
            response = await result.text()
            response_json = json.loads(response)
            if "access_token" in response_json.keys():
                return response_json["access_token"]
            else:
                print(f"Error acquiring token: {response_json.get('error')}")
                return None
    
    if "access_token" in result:
        logger.info("Access token acquired successfully")
        return result["access_token"]
    else:
        logger.error(f"Error acquiring token: {result.get('error')}")
        return None


async def get_unuploaded_documents() -> list[dict]:
    """
    Retrieve all documents that haven't been uploaded to Datev yet.
    
    Returns:
        List of document dictionaries
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    
    # Query for documents where uploadedToDatev = False
    query = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE uploadedToDatev = FALSE
    """
    
    logger.info(f"Querying for unuploaded documents from {project_id}.{dataset_id}.{table_id}")
    
    def run_query():
        """Synchronous query execution"""
        query_job = bq_client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    documents = await asyncio.to_thread(run_query)
    
    logger.info(f"Found {len(documents)} unuploaded documents")
    
    return documents

async def read_gcs_object_as_base64(gcs_uri: str) -> str:
    """
    Read an object from GCS and return its content as a base64 encoded string.
    
    Args:
        gcs_uri: The GCS URI of the object (gs://bucket-name/object-name)
    
    Returns:
        Base64 encoded content string
    """
    logger.info(f"Reading object from GCS: {gcs_uri}")
    
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    
    parts = gcs_uri[5:].split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
        
    bucket_name, blob_name = parts
    
    def read_blob():

        if credentials:

            storage_client = storage.Client(credentials=credentials, project=project_id)

        else:

            storage_client = storage.Client(project=project_id)
            
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        content = blob.download_as_bytes()
        return base64.b64encode(content).decode("utf-8")
        
    content_base64 = await asyncio.to_thread(read_blob)

    logger.info(f"Successfully read and encoded object from {gcs_uri}")

    return content_base64


## This is the email for incoming invoices
UPLOAD_INBOX_EMAIL = "jannick.kappelmann@gmail.com" #"dade80f2-1357-4f29-8583-6ff2d39e9be1@uploadmail.datev.de"


MESSAGE_TEMPLATE = {
  "message": {
    "subject": "",
    "body": {
      "contentType": "Text",
      "content": ""
    },
    "toRecipients": [
      {
        "emailAddress": {
          "address": UPLOAD_INBOX_EMAIL
        }
      }
    ],
    "attachments": [
      {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": "",
        "contentType": "",
        "contentBytes": ""
      }
    ]
  }
}

SENDER_EMAIL_DATEV="accounting-automation@massflows.de"

async def upload_document_to_datev(document: dict):
    """
    Upload a document to Datev.
    
    Args:
        document: The document dictionary to upload
    """
    
    logger.info(f"Uploading document {document['attachmentName']} to Datev")
    
    # Replace placeholders in message template
    message_template = MESSAGE_TEMPLATE.copy()
    message_template["message"]["subject"] = document["attachmentName"]
    message_template["message"]["body"]["content"] = document["attachmentName"]
    message_template["message"]["attachments"][0]["name"] = document["attachmentName"]
    message_template["message"]["attachments"][0]["contentType"] = document["attachmentType"]
    message_template["message"]["attachments"][0]["contentBytes"] = document["contentBytes"]
    

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://graph.microsoft.com/v1.0/users/{SENDER_EMAIL_DATEV}/sendMail",
            headers={
                "Authorization": f"Bearer {await get_access_token()}",
                "Content-Type": "application/json"
            },
            json=message_template
        ) as response:
            if response.status != 202:
                raise Exception(f"Failed to upload document {document['attachmentName']} to Datev: {response.text}")
    
    logger.info(f"Successfully uploaded document {document['attachmentName']} to Datev")


async def mark_documents_as_uploaded(documents: list) -> None:
    """
    Mark documents as uploaded to Datev in BigQuery.
    
    Args:
        documents: List of document dictionaries that were uploaded
    """
    if not documents:
        return

    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    
    # Extract hash IDs
    hash_ids = [f"'{doc['hashID']}'" for doc in documents if 'hashID' in doc]
    
    if not hash_ids:
        return
        
    hash_ids_str = ", ".join(hash_ids)
    
    # Update query to set uploadedToDatev = True and uploadedDatetime
    query = f"""
        UPDATE `{project_id}.{dataset_id}.{table_id}`
        SET uploadedToDatev = TRUE,
            uploadedDatetime = CAST(CURRENT_TIMESTAMP() AS STRING)
        WHERE hashID IN ({hash_ids_str})
    """
    
    logger.info(f"Marking {len(hash_ids)} documents as uploaded to Datev")
    
    def run_update():
        """Synchronous update execution"""
        query_job = bq_client.query(query)
        query_job.result()
        
    await asyncio.to_thread(run_update)
    logger.info("Successfully marked documents as uploaded")

async def mark_document_as_uploaded(document: dict) -> None:
    """
    Mark documents as uploaded to Datev in BigQuery.
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    
  
    # Update query to set uploadedToDatev = True and uploadedDatetime
    query = f"""
        UPDATE `{project_id}.{dataset_id}.{table_id}`
        SET uploadedToDatev = TRUE,
            uploadedDatetime = CAST(CURRENT_TIMESTAMP() AS STRING)
        WHERE hashID = @hash_id
    """
    

    job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("hash_id", "STRING", document['hashID'])
            ]
        )
        

    logger.info(f"Marking {document['hashID']} as uploaded to Datev")
    
    def run_update():
        """Synchronous update execution"""
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        
    await asyncio.to_thread(run_update)
    logger.info("Successfully marked documents as uploaded")


async def main():

    
    ## Get all documents which are not uploaded to datev
    documents = await get_unuploaded_documents()

    print(f"Found {len(documents)} documents to upload to Datev")
    
    ## Upload documents to datev
    for document in documents:

        content_base64 = await read_gcs_object_as_base64(document["gcsUri"])

        document["contentBytes"] = content_base64

        await upload_document_to_datev(document)
        print(f"Successfully uploaded document {document['attachmentName']} to Datev")

        await mark_document_as_uploaded(document)


if __name__ == "__main__":
    asyncio.run(main())
