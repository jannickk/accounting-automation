import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory, ProcessedDocumentAIStatus
from config.config import Config
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.models import col
from datetime import timezone,timedelta,datetime
from azure.identity import ClientSecretCredential
from typing import Generator, Any, Dict

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

def get_unprocessed_documents_from_dataverse(client: DataverseClient)-> Generator[Attachment,Any,Any]:
    ## Yield a generator for the files not yet processed in Mistral


    records = client.query.builder("acc_attachment").where(col("acc_processed_document_ai")==False).execute()

    for record in records:
        yield Attachment.model_validate(record.to_dict())
    

def get_attachments_not_uploaded_to_datev(client: DataverseClient)-> Generator[Attachment,Any,Any]:
    ## Yield a generator for the attachments not yet uploaded to DATEV

    records = client.query.builder("acc_attachment").where(col("acc_uploadedtodatev")==False).execute()

    for record in records:
        yield Attachment.model_validate(record.to_dict())


def get_creditor_id_by_name(client: DataverseClient, creditor_name:str)-> str | None:

    records = client.query.builder("acc_creditor").where(col("acc_name")==creditor_name).execute()

    record = records.first()

    if record:
        return record.data["acc_creditorid"]
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

