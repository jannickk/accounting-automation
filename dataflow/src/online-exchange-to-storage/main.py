
from typing import Optional

from google.cloud.bigquery import Client
from google.cloud.bigquery.table import RowIterator
from google.cloud import storage
from google.oauth2 import service_account
import aiohttp
import os
import json
from pathlib import Path
import asyncio
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory, ISO8601
from config.config import Config
from utility import get_email_id_by_hash_id, get_attachment_id_by_hash_id
import base64
from datetime import datetime, timezone
import hashlib
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient, ContentSettings
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.models import col
from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, stream=sys.stdout)

logger = logging.getLogger(__name__)

logger.addHandler(logging.StreamHandler(sys.stdout))

logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)


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





async def get_checkpoint_from_dataverse(config: Config)->ISO8601:
    
    client = get_dataverse_client(config)

    df = (client.query.builder("acc_email")
      .select("acc_receiveddatetime")
      .execute()
      .to_dataframe())
    
    logger.info(f"Fetched {len(df)} records from Dataverse for checkpoint calculation")
    
    if df.empty:

        checkpoint = ISO8601(value="2025-12-31T10:00:00Z")
    else:

        df = df.sort_values(by="acc_receiveddatetime", ascending=False)

        checkpoint = ISO8601(value=df.iloc[0]["acc_receiveddatetime"])

    return checkpoint


def get_filename_from_document_uri(storage_account_url: str) -> str:
    """
    This function takes as input a storage account URL in the form of
    https://invomassflowsde.blob.core.windows.net/accounts-payable/ingest/2026/8/INV00607124_A00188325_08052026.pd
    and extracts the filename from it, which is the last part of the path.
    """
    # Parse the URL to get the path
    path = storage_account_url.split("/", 3)[-1]  # Get everything after the third slash

    # Split the path into parts and return the last part as the filename
    filename = path.split("/")[-1]
    return filename


def get_directory_name_from_document_uri(storage_account_url: str) -> str:
    """
    This function takes as input a storage account URL in the form of
    https://invomassflowsde.blob.core.windows.net/accounts-payable/ingest/2026/8/INV00607124_A00188325_08052026.pd
    and extracts the filename from it, which is the last part of the path.
    """

    # Parse the URL to get the path
    path = storage_account_url.split("/", 3)[-1]  # Get everything after the third slash

    # Split the path into parts and return the last part as the filename
    directory_name = "/".join(path.split("/")[:-1])
    return directory_name

def get_container_name_from_document_uri(storage_account_url: str) -> str:
    """
    This function takes as input a storage account URL in the form of
    https://invomassflowsde.blob.core.windows.net/accounts-payable/ingest/2026/8/INV00607124_A00188325_08052026.pd
    and extracts the filename from it, which is the last part of the path.
    """

    # Parse the URL to get the path
    path = storage_account_url.split("/", 3)[-1]  # Get everything after the third slash

    # Split the path into parts and return the last part as the filename
    container_name = path.split("/")[0]
    return container_name

async def get_access_token(config: Config) -> str:


    client_id = config.GRAPH_API_CLIENT_ID
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
            logger.debug(f"Error acquiring token: {result.status}")
            return None

        else:
            response = await result.text()
            response_json = json.loads(response)
            if "access_token" in response_json.keys():
                return response_json["access_token"]
            else:
                logger.debug(f"Error acquiring token: {response_json.get('error')}")
                return None
    
    if "access_token" in result:
        return result["access_token"]
    else:
        logger.debug(f"Error acquiring token: {result.get('error')}")
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

async def get_emails_from_inbox(config: Config, checkpoint:ISO8601=None)-> list:

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
   
        params["$filter"] = f"receivedDateTime gt {checkpoint.value}"

    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/mailFolders/Inbox/messages"
    

    response_json = await get_json_from_url(
        url,
        headers=headers,
        params=params
    )

    email_list = response_json["value"]

    while "@odata.nextLink" in response_json.keys():

        logger.debug(f"Following @odata.nextLink found: {response_json['@odata.nextLink']}")

        #logger.info("Next link found")
        response_json_iter = await get_json_from_url(
            response_json["@odata.nextLink"],
            headers=headers
        )

        logger.info(f"Fetched {len(response_json_iter['value'])} emails in this iteration")
        
        email_list.extend(response_json_iter["value"])

        response_json = response_json_iter


    emails = [await get_details_of_message(config,email["id"]) for email in email_list]

    return emails

async def get_details_of_message(config:Config, email_id: str)-> dict:
    
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
    
    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/mailFolders/Inbox/messages/{email_id}"
    
    logger.debug(f"Fetching emails from: {url}")

    response_json = await get_json_from_url(
        url,
        headers=headers,
    )

    return response_json


async def get_email_attachments_from_inbox(config: Config, email_id)-> list[dict]:

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
    
    url = f"https://graph.microsoft.com/v1.0/users/{shared_email}/messages/{email_id}/attachments"
    
    logger.debug(f"Fetching attachments for email {email_id} from: {url}")
    
    response_json = await get_json_from_url(
        url,
        headers=headers
    )
    
    attachments = response_json.get("value", [])
    
    return attachments

async def upload_to_azure_datalake_storage(base64_data: str, content_type: str, container_name: str, blob_name: str) -> str:
    """
    Upload base64 encoded data to Azure Data Lake Storage Gen2.
    
    Args:
        base64_data: Base64 encoded string of the file content
        content_type: MIME content type for the file
        container_name: Name of the Data Lake filesystem
        blob_name: File path within the filesystem
    
    Returns:
        The URL of the uploaded file in Data Lake Storage
    """
    logger.info(f"Uploading {blob_name} to Data Lake filesystem {container_name}")
    
    file_data = base64.b64decode(base64_data)
    connection_string = os.environ.get("DATALAKE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("Missing DATALAKE_STORAGE_CONNECTION_STRING.")
    
    service_client = DataLakeServiceClient.from_connection_string(connection_string)
    file_system_client = service_client.get_file_system_client(container_name)
    if not file_system_client.exists():
        file_system_client.create_file_system()
    
    # Create any intermediate directories if needed.
    directory, filename = os.path.split(blob_name)
    if directory:
        directory_client = file_system_client.get_directory_client(directory)
        if not directory_client.exists():
            directory_client.create_directory()
        file_client  = directory_client.get_file_client(filename)
    else:
        file_client = file_system_client.get_file_client(filename)
    
    def upload_file():

        if not file_client.exists():
            file_client.create_file()
        file_client.upload_data(file_data, length=len(file_data),overwrite=True)
        file_client.flush_data(len(file_data))
        file_client.set_http_headers(ContentSettings(content_type=content_type))
    
    await asyncio.to_thread(upload_file)
    
    logger.info(f"Successfully uploaded {blob_name} to Data Lake filesystem {container_name}")
    return file_client.url


async def write_email_to_dataverse(config: Config, email: Email, ingest_datetime: str) -> Email:
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

    email.acc_ingesteddatetime = datetime.fromisoformat(ingest_datetime)

    hash_id = email.acc_hashid

    logger.info(f"Writing email {hash_id} to Dataverse table {email.entity_logical_name}")


    # The Dataverse SDK is synchronous; run the upsert in a thread to stay non-blocking.
    await asyncio.to_thread(email.upsert_to_dataverse, client)

    # After upsert, retrieve the record to obtain the system GUID (primary id)
    def fetch_by_alternate_key():
        try:
            result = client.records.list(
                "acc_email",
                filter=f"acc_email_alternatekey eq '{email.acc_email_alternatekey}'",
                top=1,
            )
        except Exception:
            return None
        if len(result) == 0:
            return None
        rec = result[0]
        return rec.to_dict()

    record_data = await asyncio.to_thread(fetch_by_alternate_key)

    if record_data:
        # Find the primary key field (acc_emailid) case-insensitive
        pk_key = next((k for k in record_data.keys() if k.lower() == "acc_emailid" or k.lower().endswith("emailid")), None)
        if pk_key and isinstance(record_data.get(pk_key), str):
            email.acc_emailId = record_data.get(pk_key)

    logger.info(f"Successfully wrote email {hash_id} to Dataverse (id={email.acc_emailId})")
    return email


async def write_document_to_dataverse(
    config: Config,
    attachment_model: Attachment
) -> None:
    """
    Write attachment data to the Dataverse ``acc_attachment`` table.

    Mirrors :func:`write_document`: builds an :class:`Attachment` record and upserts it
    (keyed on ``acc_hashid``). ``acc_processed_document_ai_datetime``/``acc_uploadeddatetime`` are left
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


    logger.info(
        f"Writing document record for attachment {attachment_model.acc_attachmentname} "
        f"(hash: {attachment_model.acc_hashid}) to Dataverse table {attachment_model.entity_logical_name}"
    )

    # The Dataverse SDK is synchronous; run the upsert in a thread to stay non-blocking.
    await asyncio.to_thread(attachment_model.upsert_to_dataverse, client)

    logger.info(f"Successfully wrote document record for {attachment_model.acc_attachmentname} to Dataverse")


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


async def attachment_exists_by_hash_id_dataverse(config: Config,hash_id: str,) -> bool:
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


async def get_email_by_alternate_key_dataverse(alternate_key: str, client)-> Email | None:
    """
    Fetch an email record from Dataverse by its ``acc_email_alternatekey``.


    Returns:
        The matching record (dict-like), or ``None`` if no email exists with that hash ID
    """

    def run_query()-> Email | None:
        result = (client.query.builder("acc_email")
                  .where(col("acc_email_alternatekey") == alternate_key)
                  .top(1)
                  .execute())
        if len(result) == 0:
            return None
        data = result[0].to_dict()


        return Email.model_validate(data)

    return await asyncio.to_thread(run_query)


async def get_attachment_by_alternate_key_dataverse(alternate_key: str, client)-> Attachment | None:
    """
    Fetch an attachment record from Dataverse by its ``acc_attachment_alternatekey``.


    Returns:
        The matching record (dict-like), or ``None`` if no attachment exists with that hash ID
    """

    def run_query()-> Email | None:
        result = (client.query.builder("acc_attachment")
                  .where(col("acc_attachment_alternatekey") == alternate_key)
                  .top(1)
                  .execute())
        if len(result) == 0:
            return None
        data = result[0].to_dict()


        return Attachment.model_validate(data)

    return await asyncio.to_thread(run_query)

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

async def get_email_forwarded_attachments(config: Config, email_id: str) -> list:

    ## this is a workaround to get the attachments of an email that has been forwarded
    ## as the forwarded email is not no longer SMIME signed. DATEV Send SMIME signed emails
    
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
    
    attachments = await get_email_attachments_from_inbox(config,draft_id)
    
    return attachments


async def main():

    ## Checking for the existence before writing. This is to avoid duplication in case
    ## that the checkpoint is deleted or reset and emails are processed again.

    env_path = Path(__file__).resolve().parent.parent.joinpath(".env")

    load_dotenv(env_path)

    config = Config()

    client = get_dataverse_client(config)

    checkpoint = await get_checkpoint_from_dataverse(config)

    logger.info(f"Fetching emails from checkpoint: {checkpoint}")

    print(f"Fetching emails from checkpoint: {checkpoint}")
    
    emails = await get_emails_from_inbox(config, checkpoint)

    print(f"Fetched {len(emails)} emails")

    now_iso = datetime.now(timezone.utc).isoformat()

    for email in emails:
        

        # Build the model first so the alternate key is derived by `Email.compute_alternate_key`.
        # Recomputing it here would hash the raw Graph timestamp ('...T10:30:00Z') instead of the
        # parsed datetime ('... 10:30:00+00:00') and never match the persisted records.
        candidate_email = EmailFactory.create_email(email)

        alternate_key = candidate_email.acc_email_alternatekey

        logger.info(f"Processing email from {candidate_email.acc_from_name} from {candidate_email.acc_receiveddatetime}")

        attachments = await get_email_attachments_from_inbox(config, email["id"])

        email_model = await get_email_by_alternate_key_dataverse(alternate_key,client)

        if email_model is None:


            email_model = candidate_email
            email_model.acc_numofattachments = len(attachments)

            logger.info(f"Email with alternate key {alternate_key} does not yet exist in Dataverse. However, it may be content-wise a duplicate. Checking for duplicates")

            existing_email_id= get_email_id_by_hash_id(client, email_model.acc_hashid)

            if existing_email_id:

                logger.info(f"Email from {email_model.acc_from_name} is a duplicate to email with id {existing_email_id}")

                email_model.acc_duplicate_emailid = existing_email_id


            logger.info(f"Upserting Email with  {email_model.acc_email_alternatekey}")
            
            email_model = await asyncio.to_thread(email_model.upsert_to_dataverse,client)

        else:

            logger.info(f"Email with alternate key {alternate_key} already exists, fetching from dataverse")

            email_model = await asyncio.to_thread(EmailFactory.fetch_by_alternate_key, client, alternate_key)

        # ## First determine whether any email is smime signed, in this case created a forwarded email and get the attachments from there

        curated_attachments = []

        for attachment in attachments:

            print(f"Processing attachment {attachment['name']} of type {attachment['contentType']} for email {email['id']}")

            if attachment.get("contentType") == "multipart/signed":

                attachments_unsigned = await get_email_forwarded_attachments(config,email["id"])

                curated_attachments.extend(attachments_unsigned)

            else:

                curated_attachments.append(attachment)

         # if may be that the email was written to table and a later processed failed, hence the email may already exist in the 
         # table but we need to check if the attachments exist in the GCS bucket
        for attachment in curated_attachments:

            logger.info(f"Attachment with name {attachment["name"]} is attached to Email  from {email_model.acc_from_name}")

            hash_id_attachment = hashlib.sha256(attachment.get("contentBytes").encode("utf-8")).hexdigest()

            
            container_name = "accounts-payable"
            directory = f"ingest/{email_model.acc_receiveddatetime_year}/{email_model.acc_receiveddatetime_month}"
            file_name = attachment["name"]
            storage_uri = f"{config.STORAGE_ACCOUNT_URL}/{container_name}/{directory}/{file_name}"

            attachment_candidate = AttachmentFactory.create_attachment(
                                                email=email_model,
                                                hash_id=hash_id_attachment,
                                                attachment_name=attachment['name'],
                                                attachment_type=attachment['contentType'],
                                                storage_uri=storage_uri,
                                                blob_name=file_name,
                                                directory=directory,
                                                container=container_name
                                                )

            alternate_key = attachment_candidate.acc_attachment_alternatekey

            attachment_model = await get_attachment_by_alternate_key_dataverse(alternate_key,client)


            if attachment_model:
          
                logger.info(f"Attachment with alternate_key {alternate_key} already exists, skipping")

            else:

                print("Attachment does not yet exist by alternate_key, however it may be that there is an attachment with different alternate key but identical content")

                attachment_model = attachment_candidate


                existing_attachment_id = get_attachment_id_by_hash_id(client, attachment_model.acc_hashid)

                if existing_attachment_id:

                    attachment_model.acc_duplicate_attachmentid=existing_attachment_id

                
                await upload_to_azure_datalake_storage(
                     attachment["contentBytes"],
                     attachment["contentType"],
                     container_name,
                     directory + "/" + file_name
                 )

                attachment_model = await asyncio.to_thread(attachment_model.upsert_to_dataverse, client)

    

if __name__ == "__main__":

    asyncio.run(main())


