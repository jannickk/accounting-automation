import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory, ProcessedDocumentAIStatus
from config.config import Config
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.aio import AsyncDataverseClient
from PowerPlatform.Dataverse.models import col
from datetime import timezone,timedelta,datetime
from azure.identity import ClientSecretCredential
from azure.identity.aio import ClientSecretCredential as AsyncClientSecretCredential
from typing import AsyncGenerator, Generator, Any, Dict

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

def get_async_dataverse_client(config: Config) -> AsyncDataverseClient:
    """
    Create and return an AsyncDataverseClient instance using the Dataverse configuration.

    The returned client owns an aiohttp session, so it should be used as an async
    context manager (or closed explicitly with 'await client.aclose()') to release
    the connection pool:

        async with get_async_dataverse_client(config) as client:
            async for attachment in get_attachments_to_upload_to_datev(client):
                ...

    Returns:
        AsyncDataverseClient: An instance of the AsyncDataverseClient class.
    """

    tenant_id = config.DATAVERSE_TENANT_ID
    client_id = config.DATAVERSE_CLIENT_ID
    client_secret = config.DATAVERSE_CLIENT_SECRET
    environment_url = config.DATAVERSE_ENVIRONMENT_URL

    if not all([tenant_id, client_id, client_secret, environment_url]):
        raise ValueError("Missing required Dataverse environment variables.")

    credential = AsyncClientSecretCredential(tenant_id, client_id, client_secret)
    return AsyncDataverseClient(environment_url, credential)

def get_unprocessed_documents_from_dataverse(client: DataverseClient)-> Generator[Attachment,Any,Any]:
    ## Yield a generator for the files not yet processed in Mistral


    records = client.query.builder("acc_attachment").where(col("acc_processed_document_ai")==False).execute()

    for record in records:
        print(f"Yielding attachment {record}")
        yield Attachment.model_validate(record.to_dict())
    

def get_attachments_not_uploaded_to_datev(client: DataverseClient)-> Generator[Attachment,Any,Any]:
    ## Yield a generator for the attachments not yet uploaded to DATEV

    records = client.query.builder("acc_attachment").where(col("acc_uploadedtodatev")==False).execute()


    for record in records:
        print(f"Yielding attachment {record.data['acc_name']} with ID {record.data['acc_attachmentid']}")
        yield Attachment.model_validate(record.to_dict())


async def get_attachments_to_upload_to_datev(client: AsyncDataverseClient)-> AsyncGenerator[Attachment,None]:
    """
    Yield an async generator for the attachments which still have to be uploaded to DATEV.

    An attachment qualifies when it is not yet uploaded to DATEV
    ('acc_uploadedtodatev' is False) and when it is not marked as a duplicate of
    another attachment (the 'acc_duplicate_attachmentId' lookup is empty).
    Lookup columns are filtered through their '_<logicalname>_value' form.

    The records are fetched page by page, so only one page is held in memory
    while the caller iterates. Each iteration of the underlying pager triggers
    one HTTP request, which is awaited without blocking the event loop.

    Requires an AsyncDataverseClient (see get_async_dataverse_client) and has to
    be consumed with 'async for':

        async for attachment in get_attachments_to_upload_to_datev(client):
            await upload_document_to_datev(config, attachment)
    """

    pages = (client.query.builder("acc_attachment")
             .where(col("acc_uploadedtodatev")==False)
             .where(col("acc_duplicate_attachmentId").is_null())
             .execute_pages())

    async for page in pages:
        for record in page:
            yield Attachment.model_validate(record.to_dict())


def get_creditor_id_by_name(client: DataverseClient, creditor_name:str)-> str | None:

    records = client.query.builder("acc_creditor").where(col("acc_name")==creditor_name).execute()

    record = records.first()

    if record:
        return record.data["acc_creditorid"]
    else:
        return None

def get_email_id_by_hash_id(client: DataverseClient, hash_id:str)-> str | None:
    """
    Check whether an email already exists in Dataverse for the given hash ID.

    The hash ID ('acc_hashid') is derived from the email body, so two records
    sharing it are content duplicates of each other. Use the returned GUID to
    populate the 'acc_isduplicateof' lookup of the email being ingested.

    Records that are themselves marked as duplicates are filtered out (the
    'acc_isduplicateof' lookup has to be empty), so when several emails share a
    hash ID only the original is returned instead of an arbitrary duplicate.
    Lookup columns are filtered through their '_<logicalname>_value' form.

    Args:
        client: Dataverse client used to run the query
        hash_id: The 'acc_hashid' of the email to look up

    Returns:
        The 'acc_emailid' of the existing original email with an identical hash
        ID, or None when no such email exists.
    """

    records = (client.query.builder("acc_email")
               .select("acc_emailid")
               .where(col("acc_hashid")==hash_id)
               .where(col("acc_duplicate_emailId").is_null())
               .top(1)
               .execute())

    record = records.first()

    if record:
        return record.data["acc_emailid"]
    else:
        return None

def get_attachment_id_by_hash_id(client: DataverseClient, hash_id:str)-> str | None:
    """
    Check whether an attachment already exists in Dataverse for the given hash ID.

    Mirrors get_email_id_by_hash_id for the 'acc_attachment' table: the hash ID
    ('acc_hashid') is derived from the attachment content, so two records sharing
    it are content duplicates of each other. Use the returned GUID to populate
    the 'acc_duplicate_attachmentId' lookup of the attachment being ingested.

    Records that are themselves marked as duplicates are filtered out (the
    'acc_duplicate_attachmentId' lookup has to be empty), so when several
    attachments share a hash ID only the original is returned instead of an
    arbitrary duplicate. Lookup columns are filtered through their
    '_<logicalname>_value' form.

    Args:
        client: Dataverse client used to run the query
        hash_id: The 'acc_hashid' of the attachment to look up

    Returns:
        The 'acc_attachmentid' of the existing original attachment with an
        identical hash ID, or None when no such attachment exists.
    """

    records = (client.query.builder("acc_attachment")
               .select("acc_attachmentid")
               .where(col("acc_hashid")==hash_id)
               .where(col("acc_duplicate_attachmentId").is_null())
               .top(1)
               .execute())

    record = records.first()

    if record:
        return record.data["acc_attachmentid"]
    else:
        return None

def get_id_of_transaction_currency(client: DataverseClient, transaction_currency_iso_code:str)-> str | None:

    records = client.query.builder("transactioncurrency").where(col("isocurrencycode")==transaction_currency_iso_code).execute()

    record = records.first()

    if record:
        return record.data["transactioncurrencyid"]
    else:

        return None

def update_attachment_as_successfully_processed(client: DataverseClient, attachment: Attachment)-> Attachment:


    attachment.acc_processed_document_ai=True
    attachment.acc_processed_document_ai_datetime = datetime.now(timezone.utc)
    attachment.acc_processed_document_ai_status = ProcessedDocumentAIStatus.succeeded

    return attachment.upsert_to_dataverse(client)


def update_attachment_as_uploaded_to_datev(client: DataverseClient, attachment: Attachment)-> Attachment:

    attachment.acc_uploadedtodatev = True
    attachment.acc_uploadeddatetime = datetime.now(timezone.utc)

    return attachment.upsert_to_dataverse(client)


def update_attachment_as_failed(client: DataverseClient, attachment: Attachment)-> Attachment:

    attachment.acc_processed_document_ai=True
    attachment.acc_processed_document_ai_datetime = datetime.now(timezone.utc)
    attachment.acc_processed_document_ai_status = ProcessedDocumentAIStatus.failed

    return attachment.upsert_to_dataverse(client)

