
from google.cloud.bigquery import Client
from google.cloud.bigquery.table import RowIterator
from google.cloud import storage
from google.oauth2 import service_account
import aiohttp
import os
import json
import asyncio
import logging
import sys
sys.path.append('../models')
sys.path.append('../config')
from models import Email, EmailFactory, Attachment, AttachmentFactory
from config.config import Config
import base64
from datetime import datetime, timezone
import hashlib
from azure.identity import ClientSecretCredential
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.models import col
from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

def get_dataverse_client(config: Config) -> DataverseClient:
    """
    Create and return a DataverseClient instance using environment variables for configuration.
    Returns:
        DataverseClient: An instance of the DataverseClient class.
    """

    tenant_id = config.DATAVERSE_TENANT_ID
    client_id = config.DATAVERSE_CLIENT_ID
    client_secret = config.DATAVERSE_CLIENT_SECRET
    environment_url = config.DATAVERSE_ENVIRONMENT_URL

    if not all([tenant_id, client_id, client_secret, environment_url]):
        raise ValueError("Missing required Dataverse environment variables.")

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    return DataverseClient(environment_url, credential)

def get_bigquery_client() -> Client:
    """
    Create and return a BigQuery Client instance using service account credentials from environment variables.
    
    Returns:
        google.cloud.bigquery.Client: An instance of the BigQuery Client class.
    """
    if os.environ.get("GCP_SERVICE_ACCOUNT_KEY"):
        service_account_info = json.loads(os.environ.get("GCP_SERVICE_ACCOUNT_KEY"))
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return Client(credentials=credentials, project=service_account_info.get("project_id"))
    else:
        return Client()


def run_query(client: Client, sql: str):
    job = client.query(sql)
    return list(job.result())

async def run_query_async(client: Client, sql: str):
    return await asyncio.to_thread(run_query, client, sql)

async def get_checkpoint_from_bigquery():
    
    dataset_id = os.environ.get("GCP_DATASET_ID")
    table_id = "emails"
    project_id = os.environ.get("GCP_PROJECT_ID")

    query = f"""
        SELECT MAX(receivedDateTime) as last_checkpoint
        FROM `{project_id}.{dataset_id}.{table_id}`
    """

    client = get_bigquery_client()
    result = await run_query_async(client, query)

    print(f"obtained following checkpoint {result}")

    if result[0]["last_checkpoint"]== None:
        checkpoint = "2025-11-25T10:00:00Z"
    else:
        checkpoint = result[0]["last_checkpoint"]

    return checkpoint

async def get_checkpoint_from_dataverse(config: Config):
    
    client = get_dataverse_client(config)

    df = (client.query.builder("acc_email")
      .select("acc_receiveddatetime")
      .execute()
      .to_dataframe())
    
    logger.info(f"Fetched {len(df)} records from Dataverse for checkpoint calculation")
    
    if df.empty:
        checkpoint = "2025-11-25T10:00:00Z"
    else:
        df = df.sort_values(by="acc_receiveddatetime", ascending=False)
        checkpoint = df.iloc[0]["acc_receiveddatetime"].isoformat()

    return checkpoint

def get_blob_name_for_document_uri(document_uri: str) -> str:
    
    document_uri = document_uri.replace("gs://", "").split("/")[1:]

    return "/".join(document_uri)


async def write_document(
    email_id: str,
    from_email_address_name: str,
    hash_id: str,
    attachment_name: str,
    attachment_type: str,
    gcs_uri: str
) -> None:
    """
    Write attachment data to the documents BigQuery table.
    
    Args:
        email_id: The email ID (hashID from emails table)
        hash_id: The unique hash ID for this document/attachment
        attachment_name: Name of the attachment file
        attachment_type: MIME type of the attachment (e.g., 'application/pdf')
        gcs_uri: GCS URI where the attachment is stored
        processed: Whether the document has been processed (default: False)
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    logger.info(f"Writing document record for attachment {attachment_name} (hash: {hash_id})")
    
    # Create row with all required fields
    row = {
        "emailID": email_id,
        "hashID": hash_id,
        "processedDocumentAI": False,
        "attachmentName": attachment_name,
        "attachmentType": attachment_type,
        "gcsUri": gcs_uri,
        "finalGcsUri": f"gs://{os.environ.get('GCP_BUCKET_NAME')}/processed/{from_email_address_name}/{attachment_name}",
        "blobName": get_blob_name_for_document_uri(gcs_uri),
        "finalBlobName": f"processed/{from_email_address_name}/{attachment_name}",
        "uploadedToDatev": False,
        "uploadedDatetime": None,
        "processedDatetime": None,
        "fromEmailAddressName": from_email_address_name,
        "isDuplicateOf": None
    }


    print(f"Writing following row to BigQuery table {project_id}.{dataset_id}.{table_id}: {row}")
    
    # Insert row into BigQuery
    def insert_row():
        """Synchronous insert operation"""
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")
    
    await asyncio.to_thread(insert_row)
    
    logger.info(f"Successfully wrote document record for {attachment_name} to {table_id}")


async def email_exists_by_hash_id(hash_id: str) -> bool:
    """
    Check whether an email exists in BigQuery by its hashID.
    
    Args:hash_id: The hash ID of the email to check
        hash_id: The hash ID of the email to check
    
    Returns:
        Boolean indicating whether the email exists in the emails table
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = os.environ.get("GCP_TABLE_ID", "emails")
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    logger.info(f"Checking if email with hashID {hash_id} exists")
    
    # Query for email with the given hashID
    query = f"""
        SELECT COUNT(*) as email_count
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE hashID = @hash_id
    """
    
    def run_query():
        """Synchronous query execution with parameters"""
        
        
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("hash_id", "STRING", hash_id)
            ]
        )
        
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    result = await asyncio.to_thread(run_query)
    
    exists = result[0]["email_count"] > 0
    
    logger.info(f"Email with hashID {hash_id} {'exists' if exists else 'does not exist'}")
    
    return exists


async def attachment_exists_by_hash_id(hash_id: str) -> bool:
    """
    Check whether an attachment/document exists in BigQuery by its hashID.
    
    Args:
        hash_id: The hash ID of the attachment to check
    
    Returns:
        Boolean indicating whether the attachment exists in the documents table
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    logger.info(f"Checking if attachment with hashID {hash_id} exists")
    
    # Query for attachment with the given hashID
    query = f"""
        SELECT COUNT(*) as attachment_count
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE hashID = @hash_id
    """
    
    def run_query():
        """Synchronous query execution with parameters"""
        from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
        
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("hash_id", "STRING", hash_id)
            ]
        )
        
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    result = await asyncio.to_thread(run_query)
    
    exists = result[0]["attachment_count"] > 0
    
    logger.info(f"Attachment with hashID {hash_id} {'exists' if exists else 'does not exist'}")
    
    return exists


async def get_access_token(config: Config) -> str:


    client_id = config.GRAPH_API_CLIENT_ID_CLIENT_ID
    client_secret = config.GRAPH_API_CLIENT_SECRET
    tenant_id = config.GRAPH_API_TENANT_ID
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
        return result["access_token"]
    else:
        print(f"Error acquiring token: {result.get('error')}")
        return None


async def get_json_from_url(url, headers=None, params=None)-> dict:
    async with aiohttp.ClientSession() as session:

        result = await session.get(

            url,
            headers=headers,
            params=params
        )

        if result.status != 200:
            logger.error(f"Error accesing MS graph API: {result.status}")
            raise Exception(f"Error accesing MS graph API: {result.status} and {result.reason}")

        else:
            response = await result.text()
            response_json = json.loads(response)
            return response_json

async def get_emails_from_inbox(checkpoint=None, config: Config=None)-> list:

    token = await get_access_token(config)

    if not token:
        raise Exception("Error acquiring access token")

    shared_email = os.environ.get("SHARED_MAILBOX_EMAIL")

    if not shared_email:
        raise Exception("SHARED_MAILBOX_EMAIL not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {}

    if checkpoint:
        # Checkpoint is assumed to be an ISO 8601 string, e.g., "2023-10-27T10:00:00Z"
        # OData filter for greater than
        params["$filter"] = f"receivedDateTime gt {checkpoint}"

    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/mailFolders/Inbox/messages"
    
    #logger.info(f"Fetching emails from: {url}")

    response_json = await get_json_from_url(
        url,
        headers=headers,
        params=params
    )

    email_list = response_json["value"]

    while "@odata.nextLink" in response_json.keys():

        print("Next link found")

        #logger.info("Next link found")
        response_json_iter = await get_json_from_url(
            response_json["@odata.nextLink"],
            headers=headers
        )
        #logger.info(f"Fetched {len(response_json_iter['value'])} emails in this iteration")
        
        email_list.extend(response_json_iter["value"])

        response_json = response_json_iter
        
    #logger.info(f"Fetched {len(email_list)} emails")

    emails = [await get_details_of_message(email["id"]) for email in email_list]

    return emails

async def get_details_of_message(email_id: str)-> dict:
    
    token = await get_access_token()
    
    if not token:
        raise Exception("Error acquiring access token")

    shared_email = os.environ.get("SHARED_MAILBOX_EMAIL")

    if not shared_email:
        raise Exception("SHARED_MAILBOX_EMAIL not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/mailFolders/Inbox/messages/{email_id}"
    
    logger.info(f"Fetching emails from: {url}")

    response_json = await get_json_from_url(
        url,
        headers=headers,
    )

    return response_json


async def get_email_attachments_from_inbox(email_id)-> list[dict]:

    token = await get_access_token()
    if not token:
        raise Exception("Error acquiring access token")
    
    shared_email = os.environ.get("SHARED_MAILBOX_EMAIL")
    if not shared_email:
        raise Exception("SHARED_MAILBOX_EMAIL not set")
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/messages/{email_id}/attachments"
    
    logger.info(f"Fetching attachments for email {email_id} from: {url}")
    
    response_json = await get_json_from_url(
        url,
        headers=headers
    )
    
    attachments = response_json.get("value", [])
    logger.info(f"Fetched {len(attachments)} attachments for email {email_id}")
    
    return attachments

async def upload_to_azure_blob_storage(base64_data: str, content_type: str, container_name: str, blob_name: str) -> str:
    """
    Upload base64 encoded data to Azure Blob Storage.
    
    Args:
        base64_data: Base64 encoded string of the file content
        container_name: Name of the Azure Blob Storage container
        blob_name: Name/path of the blob in the container
    
    Returns:
        The URL of the uploaded blob
    """
    logger.info(f"Uploading {blob_name} to container {container_name}")
    
    # Decode base64 data
    file_data = base64.b64decode(base64_data)
    
    # Initialize Azure Blob Service Client
    account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
    account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    
    if not account_url or not account_key:
        raise ValueError("Missing Azure Storage account URL or key.")
    
    blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)
    
    # Define upload function to run in thread
    def upload_blob():
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(file_data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
    
    # Upload using asyncio.to_thread for async operation
    await asyncio.to_thread(upload_blob)
    
    logger.info(f"Successfully uploaded {blob_name} to {container_name}")
    
    return f"{account_url}/{container_name}/{blob_name}"

async def upload_to_gcs(base64_data: str, content_type: str, bucket_name: str, object_name: str) -> str:
    """
    Upload base64 encoded data to Google Cloud Storage.
    
    Args:
        base64_data: Base64 encoded string of the file content
        bucket_name: Name of the GCS bucket
        object_name: Name/path of the object in the bucket
    
    Returns:
        The public URL of the uploaded object
    """
    logger.info(f"Uploading {object_name} to bucket {bucket_name}")
    
    # Decode base64 data
    file_data = base64.b64decode(base64_data)
    
    # Initialize GCS client
    if os.environ.get("GCP_SERVICE_ACCOUNT_KEY"):

        service_account_info = json.loads(os.environ.get("GCP_SERVICE_ACCOUNT_KEY"))

        credentials = service_account.Credentials.from_service_account_info(service_account_info)

        storage_client = storage.Client(credentials=credentials, project=service_account_info.get("project_id"))

    else:
        storage_client = storage.Client()
    
    # Define upload function to run in thread
    def upload_file():

        bucket = storage_client.bucket(bucket_name)

        blob = bucket.blob(object_name)

        blob.upload_from_string(file_data,content_type=content_type)
    
    # Upload using asyncio.to_thread for async operation
    await asyncio.to_thread(upload_file)
    
    logger.info(f"Successfully uploaded {object_name} to {bucket_name}")
    
    return f"gs://{bucket_name}/{object_name}"



async def write_email_to_dataverse(email: dict, ingest_datetime: str, numOfAttachments: int, config: Config) -> None:
    """
    Write email data to the Dataverse ``acc_email`` table.

    Mirrors :func:`write_email_to_bigquery`: builds an :class:`Email` record from the
    Microsoft Graph payload and upserts it (keyed on ``acc_hashid``) so re-ingesting the
    same email does not create a duplicate.

    Args:
        email: Email data dictionary from Microsoft Graph API
        ingest_datetime: ISO 8601 datetime string of when the email was ingested
        numOfAttachments: Number of attachments in the email
        config: Application configuration used to build the Dataverse client
    """
    client = get_dataverse_client(config)

    # Build the record from the Graph payload, then apply the values known at ingest time.
    email_model = EmailFactory.create_email(email)
    email_model.acc_numofattachments = numOfAttachments
    email_model.acc_ingesteddatetime = datetime.fromisoformat(ingest_datetime)

    hash_id = email_model.acc_hashid

    logger.info(f"Writing email {hash_id} to Dataverse table {email_model.entity_logical_name}")

    # The Dataverse SDK is synchronous; run the upsert in a thread to stay non-blocking.
    await asyncio.to_thread(email_model.write_to_dataverse, client)

    logger.info(f"Successfully wrote email {hash_id} to Dataverse")


async def write_document_to_dataverse(
    email_id: str,
    from_email_address_name: str,
    hash_id: str,
    attachment_name: str,
    attachment_type: str,
    gcs_uri: str,
    config: Config,
) -> None:
    """
    Write attachment data to the Dataverse ``acc_attachment`` table.

    Mirrors :func:`write_document`: builds an :class:`Attachment` record and upserts it
    (keyed on ``acc_hashid``). ``acc_processeddatetime``/``acc_uploadeddatetime`` are left
    unset and the boolean flags default to ``False`` because the document has only just
    been ingested.

    Args:
        email_id: The email ID (hashID from the emails table) this attachment belongs to
        from_email_address_name: Display name of the sender (kept for signature parity
            with :func:`write_document`)
        hash_id: The unique hash ID for this document/attachment
        attachment_name: Name of the attachment file
        attachment_type: MIME type of the attachment (e.g. ``application/pdf``)
        gcs_uri: Storage URI where the attachment is stored
        config: Application configuration used to build the Dataverse client
    """
    client = get_dataverse_client(config)

    attachment_model = AttachmentFactory.create_attachment(
        email_id=email_id,
        hash_id=hash_id,
        attachment_name=attachment_name,
        attachment_type=attachment_type,
        storage_uri=gcs_uri,
        blob_name=get_blob_name_for_document_uri(gcs_uri),
    )

    logger.info(
        f"Writing document record for attachment {attachment_name} "
        f"(hash: {hash_id}) to Dataverse table {attachment_model.entity_logical_name}"
    )

    # The Dataverse SDK is synchronous; run the upsert in a thread to stay non-blocking.
    await asyncio.to_thread(attachment_model.write_to_dataverse, client)

    logger.info(f"Successfully wrote document record for {attachment_name} to Dataverse")


async def email_exists_by_hash_id_dataverse(hash_id: str, config: Config) -> bool:
    """
    Check whether an email exists in Dataverse by its ``acc_hashid``.

    Mirrors :func:`email_exists_by_hash_id`.

    Args:
        hash_id: The hash ID of the email to check
        config: Application configuration used to build the Dataverse client

    Returns:
        Boolean indicating whether the email exists in the ``acc_email`` table
    """
    client = get_dataverse_client(config)

    logger.info(f"Checking if email with hashID {hash_id} exists in Dataverse")

    def run_query():
        result = (client.query.builder("acc_email")
                  .select("acc_hashid")
                  .where(col("acc_hashid") == hash_id)
                  .top(1)
                  .execute())
        return len(result) > 0

    exists = await asyncio.to_thread(run_query)

    logger.info(f"Email with hashID {hash_id} {'exists' if exists else 'does not exist'} in Dataverse")

    return exists


async def attachment_exists_by_hash_id_dataverse(hash_id: str, config: Config) -> bool:
    """
    Check whether an attachment/document exists in Dataverse by its ``acc_hashid``.

    Mirrors :func:`attachment_exists_by_hash_id`.

    Args:
        hash_id: The hash ID of the attachment to check
        config: Application configuration used to build the Dataverse client

    Returns:
        Boolean indicating whether the attachment exists in the ``acc_attachment`` table
    """
    client = get_dataverse_client(config)

    logger.info(f"Checking if attachment with hashID {hash_id} exists in Dataverse")

    def run_query():
        result = (client.query.builder("acc_attachment")
                  .select("acc_hashid")
                  .where(col("acc_hashid") == hash_id)
                  .top(1)
                  .execute())
        return len(result) > 0

    exists = await asyncio.to_thread(run_query)

    logger.info(f"Attachment with hashID {hash_id} {'exists' if exists else 'does not exist'} in Dataverse")

    return exists


async def get_email_by_hash_id_dataverse(hash_id: str, config: Config):
    """
    Fetch an email record from Dataverse by its ``acc_hashid``.

    Mirrors :func:`get_email_by_hash_id`.

    Args:
        hash_id: Hash ID of the email
        config: Application configuration used to build the Dataverse client

    Returns:
        The matching record (dict-like), or ``None`` if no email exists with that hash ID
    """
    client = get_dataverse_client(config)

    def run_query():
        result = (client.query.builder("acc_email")
                  .where(col("acc_hashid") == hash_id)
                  .top(1)
                  .execute())
        if len(result) == 0:
            return None
        return result[0]

    return await asyncio.to_thread(run_query)


async def write_email_to_bigquery(email: dict, ingest_datetime: str, numOfAttachments: int) -> None:
    """
    Write email data to BigQuery table.
    
    Args:
        email: Email data dictionary from Microsoft Graph API
    """

    client = get_bigquery_client()

    dataset_id = os.environ.get("GCP_DATASET_ID")
    table_id = "emails"
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    # Generate hash ID from email ID
    hash_id = hashlib.sha256(email.get("body").get("content").encode()).hexdigest()
    
    # Prepare row data matching the BigQuery schema
    row = {
        "subject": email.get("subject"),
        "receivedDateTime": email.get("receivedDateTime"),
        "hashID": hash_id,
        "id": email.get("id"),
        "ingestDateTime": ingest_datetime,
        "sender": email.get("sender"),
        "from": email.get("from"),
        "toRecipients": email.get("toRecipients", [{}])[0] if email.get("toRecipients") else None,
        "numOfAttachments": numOfAttachments
    }
    
    logger.info(f"Writing email {hash_id} to BigQuery table {project_id}.{dataset_id}.{table_id}")
    
    print(f"Writing following row to BigQuery: {row}")
    # Insert row using asyncio.to_thread
    def insert_row():

        table_ref = f"{project_id}.{dataset_id}.{table_id}"

        errors = client.insert_rows_json(table_ref, [row])

        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")
    
    await asyncio.to_thread(insert_row)
    
    logger.info(f"Successfully wrote email {hash_id} to BigQuery")


async def get_email_by_hash_id(hash_id: str) -> dict:
    """
    Check if email with given hash ID exists in BigQuery table.
    
    Args:
        hash_id: Hash ID of the email
    
    Returns:
        True if email exists, False otherwise
    """
    dataset_id = os.environ.get("GCP_DATASET_ID")
    table_id = "emails"
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Query to check if email exists
    query = f"SELECT * FROM `{table_ref}` WHERE hashID = '{hash_id}'"
    
    # Execute query using asyncio.to_thread
    def execute_query():
        job = client.query(query)
        return job.result()
    
    result = await asyncio.to_thread(execute_query)
    
    return result[0]

async def get_email_forwarded_attachments(email_id: str) -> list:

    ## this is a workaround to get the attachments of an email that has been forwarded
    ## as the forwarded email is not no longer SMIME signed. DATEV Send SMIME signed emails
    
    token = await get_access_token()
    
    if not token:
        raise Exception("Error acquiring access token")
    
    shared_email = os.environ.get("SHARED_MAILBOX_EMAIL")
    if not shared_email:
        raise Exception("SHARED_MAILBOX_EMAIL not set")
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/messages/{email_id}/createForward"
    
    async with aiohttp.ClientSession() as session:

        result = await session.post(
            url,
            headers=headers,
        )

        if result.status != 201:
            logger.error(f"Error accesing MS graph API: {result.status}")
            raise Exception(f"Error accesing MS graph API: {result.status} and {result.reason}")

        else:
            logger.info(f"Successfully created forward for email {email_id}")


        result_json = await result.json()
        draft_id = result_json.get("id")
    
    attachments = await get_email_attachments_from_inbox(draft_id)
    
    return attachments


async def main():

    ## Checking for the existence before writing. This is to avoid duplication in case
    ## that the checkpoint is deleted or reset and emails are processed again.

    load_dotenv("../.env")

    config = Config()

    checkpoint = await get_checkpoint_from_dataverse(config)

    logger.info(f"Fetching emails from checkpoint: {checkpoint}")
    print(f"Fetching emails from checkpoint: {checkpoint}")
    
    emails = await get_emails_from_inbox(checkpoint)

    print(f"Fetched {len(emails)} emails")

    now_iso = datetime.now(timezone.utc).isoformat()

    for email in emails:
        
        hash_id = hashlib.sha256(email.get("body").get("content").encode()).hexdigest()
        
        logger.info(f"Processing email {email['id']} with hashID {hash_id}")

        attachments = await get_email_attachments_from_inbox(email["id"])

        ## Deduplication Step
        if await email_exists_by_hash_id_dataverse(hash_id, config):

            logger.info(f"Email with hashID {hash_id} already exists, skipping")

        else:

            await write_email_to_dataverse(email, now_iso, len(attachments), config)

        # ## First determine whether any email is smime signed, in this case created a forwarded email and get the attachments from there
        

        curated_attachments = []

        for attachment in attachments:

            print(f"Processing attachment {attachment['name']} of type {attachment['contentType']} for email {email['id']}")

            if attachment.get("contentType") == "multipart/signed":

                attachments_unsigned = await get_email_forwarded_attachments(email["id"])

                curated_attachments.extend(attachments_unsigned)

            else:

                curated_attachments.append(attachment)

        # # if may be that the email was written to table and a later processed failed, hence the email may already exist in the 
        # # table but we need to check if the attachments exist in the GCS bucket
        # for attachment in curated_attachments:

        #     hash_id_attachment = hashlib.sha256(attachment.get("contentBytes").encode("utf-8")).hexdigest()

        #     if not await attachment_exists_by_hash_id(hash_id_attachment):
                
        #         await upload_to_gcs(
        #             attachment["contentBytes"],
        #             attachment["contentType"],
        #             os.environ.get("GCS_BUCKET_NAME"),
        #             f"ingest/{email['id']}/{attachment['name']}"
        #         )

        #         await write_document(
        #             email_id=email["id"],
        #             from_email_address_name=email["sender"]["emailAddress"]["name"],
        #             hash_id=hash_id_attachment,
        #             attachment_name=attachment["name"],
        #             attachment_type=attachment["contentType"],
        #             gcs_uri=f"gs://{os.environ.get('GCS_BUCKET_NAME')}/ingest/{email['id']}/{attachment['name']}"
        #         )
        #     else:
        #         logger.info(f"Attachment with hashID {hash_id_attachment} already exists, skipping")
        #         print(f"Attachment with hashID {hash_id_attachment} already exists, skipping")
    

if __name__ == "__main__":

    asyncio.run(main())


