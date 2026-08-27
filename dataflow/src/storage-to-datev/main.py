import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import os
import json
import logging
import base64
import aiohttp

logger = logging.getLogger(__name__)



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
