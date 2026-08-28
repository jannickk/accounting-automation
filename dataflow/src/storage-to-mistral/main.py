
## How can the OCR

import os
import mistralai
from mistralai.client import Mistral
from mistralai.client.models import OCRResponse
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient, FileSystemClient, DataLakeDirectoryClient, DataLakeFileClient
from azure.storage.filedatalake import generate_file_sas, FileSasPermissions
import requests
import base64
from mistralai.client.chat_completion_events import ChatCompletionEvents
import json
from PowerPlatform.Dataverse import DataverseClient
import asyncio
import urllib
from datetime import timezone,timedelta,datetime
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory, DocumentData, Document
from utility import copy_file_from_one_folder_to_another,update_attachment_as_successfully_processed
from config.config import Config
from utility.dataverse import *
from dotenv import load_dotenv
from pathlib import Path


from enum import Enum, IntEnum
from pydantic import BaseModel
from typing import Annotated
from annotated_types import Gt, Ge



def list_connectors(client: Mistral) -> list[Any]:
    """List all connectors using the Mistral client. """
    try:
        return client.beta.connectors.list()
    except Exception as e:
        print(f"Error listing connectors: {e}")
        return []

# A Connector is identified using the Server URL
def get_connector_by_name(client: Mistral, name):
    """Return the first connector matching the server_url, or None if not found."""
    connectors = list_connectors(client)
    
    print(f"Found following connectors: {connectors}")
    for connector in connectors.items:
        # Some SDKs return dicts, some objects; handle both
        print(type(connector))
        print(f"Name: {connector.name} | ID: {connector.id} | Status: {connector.visibility}")

        if connector.name == name:
            return connector
    return None

def get_or_create_connector(client, name, description, server, visibility, auth_data):
    """Get existing connector for server, or create if not exists."""
    connector = get_connector_by_name(client, name)
    if connector:
        print(f"Found existing connector for name: {name}")

        print(f"Connector targets following server: {getattr(connector,"server",None)}")

        return connector
    return client.beta.connectors.create(
        name=name,
        description=description,
        server=server,
        visibility=visibility,
        auth_data=auth_data,
    )


def get_short_lived_sas_url(service_client: DataLakeServiceClient, filesystem_name, directory_name, file_name)-> str:
    

    start_time = datetime.now(timezone.utc)
    expiry_time = start_time + timedelta(minutes=10)


    with service_client.get_file_system_client(file_system=filesystem_name) as filesystem_client:

        with filesystem_client.get_directory_client(directory_name) as directory_client:

            sas_token = generate_file_sas(
                    account_name = service_client.account_name,
                    file_system_name = filesystem_name,
                    directory_name = directory_name,
                    file_name = file_name,
                    credential=service_client.credential.account_key,
                    permission=FileSasPermissions(read=True),
                    expiry=expiry_time,
                )

            with directory_client.get_file_client(file_name) as file_client:

                sas_url = f"{file_client.url}?{sas_token}"

                return sas_url


if __name__=="__main__":

    # List all local image files and group them by claim number
    #image_files = [f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith((".pdf"))]

    # Ensure output directory exists before writing Markdown files

    env_path = Path(__file__).resolve().parent.parent.joinpath(".env")
    load_dotenv(env_path)

    config = Config()
    logger = logging.getLogger(__name__)

    dataverse_client = get_dataverse_client(config)
    mistral_client = Mistral(api_key=config.MISTRAL_API_KEY)


    attachments_to_process:Generator[Attachment, Any,Any] = get_unprocessed_documents_from_dataverse(dataverse_client)
    ## Upload the attachment to an azure blob storage
    
    service = DataLakeServiceClient.from_connection_string(conn_str=config.DATALAKE_STORAGE_CONNECTION_STRING)


    print("Trying to create connector")
    
    dataverse_connector = get_or_create_connector(
        client=mistral_client,
        name="dataverse_connector",
        description="Dataverse Environment that contains creditors",
        server=config.DATAVERSE_MCP_ENDPOINT,
        visibility="shared_workspace",
        auth_data={
            "client_id": config.MISTRAL_MCP_CLIENT_ID,
            "client_secret": config.MISTRAL_MCP_CLIENT_SECRET
        },
    )



    for attachment in attachments_to_process:

        sas_url = get_short_lived_sas_url(service,attachment.acc_container,attachment.acc_directory,attachment.acc_blobname)


        messages = [
            {
                "role": "system",
                "content": """
                            You are an expert data extractor. 
                            Extract the contents into a structured JSON format following the user's template. 
                            The debitor is always massflows UG. 
                            The possible values for the creditor names are to be found in table `acc_creditor` using the Dataverse connector using the following query `SELECT acc_name FROM acc_creditor`.
                            The possible values for transcarion currency can be extracted from the `transactioncurrency` entity using the Dataverse connector tooling using the query `SELECT transactioncurrencyid, currencyname, isocurrencycode, currencysymbol FROM transactioncurrency`.
                            """
            },
            {
                "role": "user",
                "content": [
                                {
                                    "type": "text", 
                                    "text": f"Extract invoice information into a structured JSON with the following schema: {DocumentData.model_json_schema()}"
                                },
                                {
                                    "type": "document_url",
                                    "document_url": f"{sas_url}"
                                }
                            ]
            }
        ]

                
        ## When the document is sent is sent as base64 encoded binary data in the prompt, sooner or later you run into the error:      
        ## mistralai.client.errors.sdkerror.SDKError: API error occurred: Status 400. Body: {"object":"error","message":"Prompt contains 159202 tokens and 0 draft tokens, too large for model with 131072 maximum context length","type":"invalid_request_invalid_args","param":null,"code":"3051","raw_status_code":400}

        response = mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=messages,
            response_format={"type": "json_object"},
            tools=[{"type": "connector", "connector_id": dataverse_connector.id}]
        )


        choices = getattr(response,"choices")


        print(f"found the following choices {len(choices)}")

        if len(choices)==1:

            # Request just demands one choice, hence the first can be used
            messages = getattr(choices[0],"messages",None)

            if messages:

              ## if an error occurs in any document
            
                if any(["error" in message.content for message in messages]):

                    print(f"Error processing attachment {attachment.acc_storageaccounturi}")

                    update_attachment_as_failed(dataverse_client, attachment)

                    ## TODO Mark processing of attachment as failed in Dataverse
                    continue
            
                else:

                    print(f"Extracted document information from document {attachment.acc_storageaccounturi}")



                    ## Try find the message with the extraction result

                    message_index = None

                    for ind, message in enumerate(messages):

                        content = getattr(message,"content",'')

                        if (message.role == "assistant") and (content !='') and (content !={}):

                            message_index=ind

                    if message_index:
                        
                        message = messages[message_index]

                        print(f"{message.role},{message.content},{message.tool_calls}")

                        extracted:DocumentData = DocumentData.model_validate_json(message.content)

                        ## Lookup id of creditor based on the extracted name
                        creditor_id = get_creditor_id_by_name(dataverse_client, extracted.creditor)

                        ## Lookup transaction currency based on the extracted isocode
                        transaction_currency_id = get_id_of_transaction_currency(dataverse_client, extracted.transaction_currency)

                        if ((creditor_id == None) or (transaction_currency_id == None)):

                            print("Successfully extarcted data from document")
                            print("However creditor or transaction currency extracted could not be found in Master data table")
                            update_attachment_as_failed(dataverse_client, attachment)

                        else:

                            document:Document = Document(
                                                acc_attachmentId = attachment.acc_attachmentId,
                                                acc_creditorId = creditor_id,
                                                acc_transactioncurrencyId = transaction_currency_id,
                                                acc_invoice_date= extracted.date_of_invoice,
                                                acc_gross_amount= extracted.total_amount,
                                                acc_net_amount= extracted.net_amount,
                                                acc_vat_amount=extracted.total_amount_of_taxes_paid,
                                                acc_invoice_id = extracted.invoice_number,
                                                acc_products_and_services_received = " , ".join([str(item) for item in [extracted.products_services_received] if extracted.products_services_received is not None])
                                    )

                            document:Document = document.upsert_to_dataverse(dataverse_client)

                            asyncio.run(copy_file_from_one_folder_to_another(
                                                                                        config,
                                                                                        source_path = attachment.acc_directory+"/"+str(attachment.acc_blobname),
                                                                                        target_path = extracted.creditor+"/"+ str(document.acc_invoice_year)+"/"+str(attachment.acc_blobname),
                                                                                        container = attachment.acc_container
                                                                                     )
                                                                                     )

                            print(f"Successfully upserted: {attachment.acc_storageaccounturi}")

                            update_attachment_as_successfully_processed(dataverse_client, attachment)

                    else:

                        print("No Message from assistent found that has non-zero content")