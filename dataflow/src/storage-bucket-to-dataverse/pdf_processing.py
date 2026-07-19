
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
import json
import urllib
import datetime
from datetime import timezone,timedelta,datetime
import logging


logger = logging.getLogger(__name__)


PDF_DIRECTORY="../pdfs/"
PDF_OUTPUT_DIRECTORY="../pdf-output-directory"
MISTRAL_API_KEY="idoM2jwzRdto1mH5ds5WcXeaeG8tSez3"
DATALAKE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=invomassflowsde;AccountKey=XmGEGOUt6PxOXqJXeuDQFYDqdF8nFjl2RrlXbAKwGoc4xmE8Ii9EV4Voj462yBesHPzCt6Z/LqCN+ASts3KNIA==;EndpointSuffix=core.windows.net"
CONTAINER_NAME="invoices"
DIRECTORY="unprocessed"

if not MISTRAL_API_KEY:

    print("⚠️  WARNING: No API key found!")

dataverse_connector = client.beta.connectors.create(

else:
    client = Mistral(api_key=MISTRAL_API_KEY)
    print("✅ Mistral client initialized")


# --- Connector Management ---
def list_connectors(client):
    """List all connectors using the Mistral client."""
    try:
        return client.beta.connectors.list()
    except Exception as e:
        print(f"Error listing connectors: {e}")
        return []

def get_connector_by_server(client, server_url):
    """Return the first connector matching the server_url, or None if not found."""
    connectors = list_connectors(client)
    for connector in connectors:
        # Some SDKs return dicts, some objects; handle both
        conn_server = getattr(connector, 'server', None) or connector.get('server')
        if conn_server == server_url:
            return connector
    return None

def get_or_create_connector(client, name, description, server, visibility, auth_data):
    """Get existing connector for server, or create if not exists."""
    connector = get_connector_by_server(client, server)
    if connector:
        print(f"✅ Found existing connector for {server}")
        return connector
    print(f"➕ Creating new connector for {server}")
    return client.beta.connectors.create(
        name=name,
        description=description,
        server=server,
        visibility=visibility,
        auth_data=auth_data,
    )

# Use the new logic to get or create the connector
dataverse_connector = get_or_create_connector(
    client=client,
    name="dataverse_connector",
    description="Dataverse Environment that contains creditors",
    server="https://org374e9080.crm4.dynamics.com/api/mcp",
    visibility="shared_workspace",
    auth_data={
        "client_id": "2cb1c1e1-6f35-4bbc-a0aa-699e5bde0299",
        "client_secret": "rhe8Q~HbRQlBMP6s1fRvRN_bJ~Zi_yShjU4kNcko"
    },
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

def get_short_lived_sas_url(service_client: DataLakeServiceClient, file_client, filesystem_name, directory_name, file_name):
    

    start_time = datetime.now(timezone.utc)
    expiry_time = start_time + timedelta(minutes=10)

    sas_token = generate_file_sas(
        account_name = service_client.account_name,
        file_system_name = filesystem_name,
        directory_name = directory_name,
        file_name = file_name,
        credential=service_client.credential.account_key,
        permission=FileSasPermissions(read=True),
        expiry=expiry_time,
    )

    sas_url = f"{file_client.url}?{sas_token}"

    return sas_url



if __name__=="__main__":

    # List all local image files and group them by claim number
    image_files = [f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith((".pdf"))]

    # Ensure output directory exists before writing Markdown files
    os.makedirs(PDF_OUTPUT_DIRECTORY, exist_ok=True)

    ## Upload the file to an azure blob storage
    

    service = DataLakeServiceClient.from_connection_string(conn_str=DATALAKE_STORAGE_CONNECTION_STRING)

    INVOICE_DIRECTORY="invoices"

    for file in image_files:

        file_systems = service.list_file_systems()

        if not CONTAINER_NAME in [filesystem.name for filesystem in file_systems]:

            service.create_file_system(CONTAINER_NAME)
        
        file_system_client = service.get_file_system_client(file_system=CONTAINER_NAME)

        # 3. Get the Directory Client
        directory_client = file_system_client.get_directory_client(DIRECTORY)


        file_client = directory_client.get_file_client(file)

        if not file_client.exists():
        

            file_client = directory_client.create_file(file)

            local_path=PDF_DIRECTORY+"/"+file

            with open(local_path, "rb") as data:

                file_length = os.path.getsize(local_path)

                file_client.append_data(data, offset=0, length=file_length)

                file_client.flush_data(file_length)
                

        sas_url = get_short_lived_sas_url(service,file_client,CONTAINER_NAME,DIRECTORY,file)

        print(sas_url)

        print(f"Reading out the file: {file}")
        

        base64_pdf = encode_pdf(PDF_DIRECTORY+"/"+file)

        # Call the OCR API
        pdf_response:OCRResponse = client.ocr.process(
        
                                             model="mistral-ocr-latest",
                                            document={
                                                        "type": "document_url",
                                                        "document_url": f"data:application/pdf;base64,{base64_pdf}"
                                                    },
                                            include_image_base64=True,
                                            table_format="html" #Specify HTML format to render complex table formats
                                        )

        # Convert response to JSON format
        response_dict = json.loads(pdf_response.model_dump_json())

        print(response_dict)

        with open(PDF_OUTPUT_DIRECTORY+"/ocr_result_"+file+"_.md","w") as f:
            f.writelines(pdf_response.pages[0].markdown)

        ## Do the same with a system prompt

        ### Passing the entire base64 encoded serialized pdf into the request leads to context length overflow

        ## mistralai.client.errors.sdkerror.SDKError: API error occurred: Status 400. Body: {"object":"error","message":"Prompt contains 159202 tokens and 0 draft tokens, too large for model with 131072 maximum context length","type":"invalid_request_invalid_args","param":null,"code":"3051","raw_status_code":400}


        # Example message structure for Document Intelligence
        messages = [
            {
                "role": "system",
                "content": "You are an expert data extractor. Extract the contents into a structured JSON format following the user's template. The debitor is always massflows UG. The possible values for the creditors can be extracted from the acc_creditors table from Dataverse using the Tools"
            },
            {
                "role": "user",
                "content": [
                                {
                                    "type": "text", 
                                    "text": """
                                                Extract invoice information into a structured JSON with the following information:
                                                    - creditor
                                                    - date of the invoice
                                                    - the period of service
                                                    - the debitor (which is always massflows UG).
                                                    - total amount of invoice (not individual positions)
                                                    - applicale taxes if any
                                            """
                                },
                                {
                                    "type": "document_url",
                                    "document_url": f"{sas_url}"
                                }
                            ]
            }
        ]

        response = client.chat.complete(
            model="pixtral-large-latest", # Or your specific document model
            messages=messages,
            response_format={"type": "json_object"},
            tools=[{"type": "connector", "connector_id": dataverse_connector.id}]
        )


        #response = client.beta.conversations.start_async(
        #    model="mistral-medium-latest",
        #    inputs="Which enterprise accounts renewed last quarter?",
        #    tools=[{"type": "connector", "connector_id": dataverse_connector.id}],
        #)


        print(response.model_dump_json())