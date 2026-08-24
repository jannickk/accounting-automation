import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory
from config.config import Config
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.models import col
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

def get_unprocessed_documents_from_dataverse(client: DataverseClient)-> Generator[Dict,Any,Any]:
    ## Yield a generator for the files not yet processed in Mistral

    records = client.query.builder("acc_attachment").select("acc_container",
                                                 "acc_directory", 
                                                 "acc_blobname").where(col("acc_processeddocumentai")==False).execute()

    for record in records:
        yield {
            "container": record.get("acc_container"),
            "directory": record.get("acc_directory"),
            "blob_name": record.get("acc_blobname")
        }

