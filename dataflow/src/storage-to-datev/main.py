import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Attachment
from utility import download_file_from_azure_storage, get_access_token_for_graph_api, get_attachments_not_uploaded_to_datev
from config import Config
import asyncio
import os
from utility.dataverse import *
import json
from pathlib import Path
from dotenv import load_dotenv
import logging
import base64
import aiohttp

logger = logging.getLogger(__name__)



MESSAGE_TEMPLATE = {
  "message": {
    "subject": "",
    "body": {
      "contentType": "",
      "content": ""
    },
    "toRecipients": [
      {
        "emailAddress": {
          "address": ""
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


async def upload_document_to_datev(config: Config, attachment: Attachment):
    """
    Upload a document to Datev.
    
    Args:
        document: The document dictionary to upload
    """
    
    logger.info(f"Uploading document {attachment.acc_blobname} to Datev")
    
    # Replace placeholders in message template
    message_template = MESSAGE_TEMPLATE.copy()
    message_template["message"]["subject"] = attachment.acc_blobname
    message_template["message"]["toRecipients"][0]["emailAddress"]["address"]=config.UPLOAD_INBOX_EMAIL
    message_template["message"]["body"]["content"] = attachment.acc_blobname
    message_template["message"]["body"]["contentType"] = "Text"
    message_template["message"]["attachments"][0]["name"] = attachment.acc_blobname
    message_template["message"]["attachments"][0]["contentType"] = attachment.acc_attachmenttype

    downloaded_bytes = await download_file_from_azure_storage(config,attachment.acc_directory+"/"+attachment.acc_blobname,attachment.acc_container)

    message_template["message"]["attachments"][0]["contentBytes"] = base64.b64encode(downloaded_bytes).decode("utf-8")

    print(message_template)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://graph.microsoft.com/v1.0/users/{config.SENDER_EMAIL_DATEV}/sendMail",
            headers={
                "Authorization": f"Bearer {await get_access_token_for_graph_api(config)}",
                "Content-Type": "application/json"
            },
            json=message_template
        ) as response:
            if response.status != 202:
                raise Exception(f"Failed to upload document {attachment.acc_storageaccounturi} to Datev: {response.text}")
    
    logger.info(f"Successfully uploaded document {attachment.acc_storageaccounturi} to Datev")


async def main():


    env_path = Path(__file__).resolve().parent.parent.joinpath(".env")
    load_dotenv(env_path)

    config = Config()
    logger = logging.getLogger(__name__)

    dataverse_client_async = get_async_dataverse_client(config)

    dataverse_client_sync = get_dataverse_client(config)
    
    attachments = get_attachments_to_upload_to_datev(dataverse_client_async)
    
    ## Upload documents to datev
    async for attachment in attachments:

        try:
          await upload_document_to_datev(config, attachment)
          print(f"Successfully uploaded document {attachment.acc_storageaccounturi} to Datev")

          asyncio.to_thread(update_attachment_as_uploaded_to_datev(dataverse_client_sync, attachment))

        except Exception:
            print(f"Failed on file {attachment.acc_storageaccounturi}")

    await dataverse_client_async.aclose()

       
if __name__ == "__main__":
    asyncio.run(main())
