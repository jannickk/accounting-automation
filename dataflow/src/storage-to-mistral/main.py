
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
import urllib
import datetime
from datetime import timezone,timedelta,datetime
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Email, EmailFactory, Attachment, AttachmentFactory
from config.config import Config
from utility.dataverse import *
from dotenv import load_dotenv
from pathlib import Path






PDF_DIRECTORY="../pdfs/"
PDF_OUTPUT_DIRECTORY="../pdf-output-directory"

CONTAINER_NAME="invoices"
DIRECTORY="unprocessed"




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



def encode_pdf(pdf_path)-> str:

    """Encode the pdf to base64."""
    try:
        with open(pdf_path, "rb") as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file {pdf_path} was not found.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

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


    attachments_to_process = get_unprocessed_documents_from_dataverse(dataverse_client)
    ## Upload the file to an azure blob storage
    
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



    for file in attachments_to_process:

        
        sas_url = get_short_lived_sas_url(service,file["container"],file["directory"],file["blob_name"])


        # if not CONTAINER_NAME in [filesystem.name for filesystem in file_systems]:

        #     service.create_file_system(CONTAINER_NAME)
        
        # file_system_client = service.get_file_system_client(file_system=CONTAINER_NAME)

        # # 3. Get the Directory Client
        # directory_client = file_system_client.get_directory_client(DIRECTORY)


        # file_client = directory_client.get_file_client(file)

        # if not file_client.exists():
        
        #     file_client = directory_client.create_file(file)

        #     local_path=PDF_DIRECTORY+"/"+file

        #     with open(local_path, "rb") as data:

        #         file_length = os.path.getsize(local_path)

        #         file_client.append_data(data, offset=0, length=file_length)

        #         file_client.flush_data(file_length)
                

        # sas_url = get_short_lived_sas_url(service,file_client,CONTAINER_NAME,DIRECTORY,file)

        # print(sas_url)

        # print(f"Reading out the file: {file}")
        

        # base64_pdf = encode_pdf(PDF_DIRECTORY+"/"+file)

        # Call the OCR API
        #pdf_response:OCRResponse = mistral_client.ocr.process(
        #
        #                                     model="mistral-ocr-latest",
        #                                    document={
        #                                                "type": "document_url",
        #                                                "document_url": f"data:application/pdf;base64,{base64_pdf}"
        #                                            },
        #                                    include_image_base64=True,
        #                                    table_format="html" #Specify HTML format to render complex table formats
        #                                )

        # Convert response to JSON format
        #response_dict = json.loads(pdf_response.model_dump_json())

        #print(response_dict)

        #with open(PDF_OUTPUT_DIRECTORY+"/ocr_result_"+file+"_.md","w") as f:
        #    f.writelines(pdf_response.pages[0].markdown)

        ## Do the same with a system prompt

        ### Passing the entire base64 encoded serialized pdf into the request leads to context length overflow

        ## mistralai.client.errors.sdkerror.SDKError: API error occurred: Status 400. Body: {"object":"error","message":"Prompt contains 159202 tokens and 0 draft tokens, too large for model with 131072 maximum context length","type":"invalid_request_invalid_args","param":null,"code":"3051","raw_status_code":400}


        # Example message structure for Document Intelligence
        messages = [
            {
                "role": "system",
                "content": """
                            You are an expert data extractor. 
                            Extract the contents into a structured JSON format following the user's template. 
                            The debitor is always massflows UG. 
                            The possible values for the creditor names are to be found in table `acc_creditor` using the Dataverse connector using the following query `SELECT acc_name FROM acc_creditor`.
                            The possible values for transcarion currency can be extracted from the `transactioncurrency` entity using the Dataverse connector tooling using the query `SELECT transactioncurrencyid, currencyname, isocurrencycode, currencysymbol FROM transactioncurrency`.
                            Please use English for all return field keys
                            """
            },
            {
                "role": "user",
                "content": [
                                {
                                    "type": "text", 
                                    "text": """
                                                Extract invoice information into a structured JSON with the following information
                                                    - creditor
                                                    - date of the invoice
                                                    - the period of service with start and end date
                                                    - the debitor (which is always massflows UG).
                                                    - total amount of invoice (not individual positions)
                                                    - total amount of taxes paid (if any)
                                                    - the invoice number
                                                    - the products / services received
                                                    - the transaction currency of the document
                                            """
                                },
                                {
                                    "type": "document_url",
                                    "document_url": f"{sas_url}"
                                }
                            ]
            }
        ]

        response = mistral_client.chat.complete(
            model="mistral-large-latest", # Or your specific document model
            messages=messages,
            response_format={"type": "json_object"},
            tools=[{"type": "connector", "connector_id": dataverse_connector.id}]
        )
        choices = getattr(response,"choices")


        print(f"found the following choices {len(choices)}")
        if len(choices)==1:

            print(choices[0])

            messages = getattr(choices[0],"messages",None)

            if messages:

              ## if an error occurs in any document
            
                if any(["error" in message.content for message in messages]):
                    print(f"Error processing fiel {file["blob_name"]}")

                    ## TODO Mark processing of file as failed in Dataverse
                    continue
            
                else:

                    print(f"Extract document information from document {file["blob_name"]}")

                for message in messages:

                    # messages will contain tool call results
                    if not message.tool_calls:
                        print(f"{message.role},{message.content},{message.tool_calls}")

