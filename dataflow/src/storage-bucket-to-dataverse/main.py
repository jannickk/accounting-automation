from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from google.cloud.bigquery import Client as BigQueryClient, QueryJobConfig
from google.oauth2 import service_account
import asyncio
import os
import json
import logging
from google.api_core.client_options import ClientOptions # type: ignore

logger = logging.getLogger(__name__)

# Initialize credentials
if os.environ.get("GCP_SERVICE_ACCOUNT_KEY"):
    service_account_info = json.loads(os.environ.get("GCP_SERVICE_ACCOUNT_KEY"))
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    project_id = service_account_info.get("project_id")
    bq_client = BigQueryClient(credentials=credentials, project=project_id)
else:
    credentials = None
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("DOCUMENT_AI_LOCATION", "eu")
    bq_client = BigQueryClient(project=project_id)


async def get_unprocessed_documents() -> list:
    """
    Retrieve all unprocessed documents from BigQuery.
    
    Returns:
        List of document dictionaries that haven't been processed yet
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    project_id = os.environ.get("GCP_PROJECT_ID")
    # Query for documents where processed = False
    query = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE processedDocumentAI = FALSE AND attachmentType = 'application/pdf'
    """
    
    logger.info(f"Querying for unprocessed documents from {project_id}.{dataset_id}.{table_id}")
    
    def run_query():
        print(query)

        """Synchronous query execution"""
        query_job = bq_client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    documents = await asyncio.to_thread(run_query)
    
    logger.info(f"Found {len(documents)} unprocessed documents")
    
    return documents


async def does_document_hash_id_exist(document_hash_id: str) -> bool:
    """
    Retrieve all attachments for a specific email from BigQuery.
    
    Args:
        document_hash_id: The document hash ID to check for existence
    
    Returns:
        Boolean indicating whether the document hash ID exists in the BigQuery table
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    accounting_info_table = "accounting_info"
    
    # Query for attachments matching the email ID
    query = f"""
        SELECT COUNT(document_hash_id) as document_count
        FROM `{project_id}.{dataset_id}.{accounting_info_table}`
        WHERE document_hash_id = @document_hash_id
    """
    
    logger.info(f"Querying for document hash ID {document_hash_id}")
    
    def run_query():
        """Synchronous query execution with parameters"""
        from google.cloud.bigquery import ScalarQueryParameter
        
        job_config = type('obj', (object,), {
            'query_parameters': [
                ScalarQueryParameter("document_hash_id", "STRING", document_hash_id)
            ]
        })()
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    result = await asyncio.to_thread(run_query)
    
    logger.info(f"Found {len(result)} document hash ID {document_hash_id}")
    
    return result[0]["document_count"] > 0


async def accounting_info_exists_by_document_hash_id(document_hash_id: str) -> bool:
    """
    Check whether accounting info exists for a document by its document_hash_id.
    
    Args:
        document_hash_id: The document hash ID to check in the accounting_info table
    
    Returns:
        Boolean indicating whether accounting info exists for this document
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "accounting_info"
    
    logger.info(f"Checking if accounting info exists for document_hash_id {document_hash_id}")
    
    # Query for accounting info with the given document_hash_id
    query = f"""
        SELECT COUNT(*) as record_count
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE document_hash_id = @document_hash_id
    """
    
    def run_query():
        """Synchronous query execution with parameters"""
        from google.cloud.bigquery import ScalarQueryParameter
        
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("document_hash_id", "STRING", document_hash_id)
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    
    # Run query in thread pool
    result = await asyncio.to_thread(run_query)
    
    exists = result[0]["record_count"] > 0
    
    logger.info(f"Accounting info for document_hash_id {document_hash_id} {'exists' if exists else 'does not exist'}")
    
    return exists


async def write_accounting_info(document_ai_result: dict, gcs_uri: str, document_hash_id: str, from_email_address_name: str) -> None:
    """
    Write extracted invoice data from Document AI to the accounting_info BigQuery table.
    
    Args:
        document_ai_result: The result dictionary from process_document_with_ai
        gcs_uri: The GCS URI of the processed document
        document_hash_id: The hash ID of the processed document
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "accounting_info"
    
    logger.info(f"Writing accounting info for document {gcs_uri}")
    
    # Initialize row with default values
    row = {
        "GcsUri": gcs_uri,
        "document_hash_id": document_hash_id,
        "fromEmailAddressName": from_email_address_name,
        "net_amount": None,
        "net_amount_confidence": None,
        "invoice_id": None,
        "invoice_id_confidence": None,
        "invoice_day": None,
        "invoice_month": None,
        "invoice_year": None,
        "total_amount": None,
        "total_amount_confidence": None,
        "supplier_tax_id": None,
        "supplier_tax_id_confidence": None,
        "currency": None,
        "currency_confidence": None,
        "period_of_service_year": None,
        "period_of_service_month": None,
        "supplier_iban": None,
        "supplier_iban_confidence": None,
        "invoice_date": None,
        "invoice_date_confidence": None,
        "supplier_email": None,
        "supplier_email_confidence": None,
        "supplier_address": None,
        "supplier_address_confidence": None,
        "supplier_name": None,
        "supplier_name_confidence": None,
        "supplier_registration": None,
        "supplier_registration_confidence": None,
    }
    
    # Map entity types to field names
    entity_mapping = {
        "net_amount": "net_amount",
        "invoice_id": "invoice_id",
        "total_amount": "total_amount",
        "supplier_tax_id": "supplier_tax_id",
        "currency": "currency",
        "supplier_iban": "supplier_iban",
        "invoice_date": "invoice_date",
        "supplier_email": "supplier_email",
        "supplier_address": "supplier_address",
        "supplier_name": "supplier_name",
        "supplier_registration": "supplier_registration",
    }
    
    # Extract entities from Document AI result
    for entity in document_ai_result.get("entities", []):

        entity_type = entity.get("type", "").lower()
        
        # Check if this entity type is in our mapping
        if entity_type in entity_mapping:

            field_name = entity_mapping[entity_type]

            confidence = entity.get("confidence", 0.0)
            
            # Extract value based on entity type
            if entity_type in ["net_amount", "total_amount"]:
                
                # For monetary amounts, try to extract numeric value
                row[field_name] = float(entity.get("normalized_value").get("float_value"))

                print("row field value", row[field_name])

            elif entity_type == "invoice_date":

                # For dates, use normalized value if available
                if entity.get("normalized_value") and entity["normalized_value"].get("date"):

                    date_val = entity["normalized_value"]["date"]

                    row[field_name] = f"{date_val.get('year', '')}-{date_val.get('month', ''):02d}-{date_val.get('day', ''):02d}"
                    row["invoice_year"] = date_val.get('year', '')
                    row["invoice_month"] = date_val.get('month', '')
                    row["invoice_day"] = date_val.get('day', '')
                else:

                    row[field_name] = entity.get("mention_text")
            else:
                # For text fields, use mention_text
                row[field_name] = entity.get("mention_text")
            
            # Set confidence
            row[f"{field_name}_confidence"] = confidence
    
    logger.info(f"Extracted {sum(1 for k, v in row.items() if v is not None and not k.endswith('_confidence'))} fields from document")

    # Insert row into BigQuery
    def insert_row():
        """Synchronous insert operation"""
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")
    
    await asyncio.to_thread(insert_row)
    
    logger.info(f"Successfully wrote accounting info for {gcs_uri}")


async def mark_document_as_processed(document_hash_id: str) -> None:
    """
    Update a document's processed status to True based on its hash ID.
    
    Args:
        document_hash_id: The hash ID of the document to mark as processed
    """
    dataset_id = os.environ.get("GCP_DATASET_ID", "accounting")
    table_id = "documents"
    
    logger.info(f"Marking document with hashID {document_hash_id} as processed")
    
    # Update query to set processed = True for the given hash ID
    query = f"""
        UPDATE `{project_id}.{dataset_id}.{table_id}`
        SET processedDocumentAI = TRUE,
            processedDatetime = CAST(CURRENT_TIMESTAMP() AS STRING)
        WHERE hashID = @document_hash_id
    """
    
    def run_update():
        """Synchronous update operation with parameters"""
        from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
        
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("document_hash_id", "STRING", document_hash_id)
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        # Wait for the query to complete
        query_job.result()
        
        # Get number of rows affected
        return query_job.num_dml_affected_rows
    
    # Run update in thread pool
    rows_affected = await asyncio.to_thread(run_update)
    
    logger.info(f"Marked {rows_affected} document(s) with hashID {document_hash_id} as processed")
    
    if rows_affected == 0:
        logger.warning(f"No documents found with hashID {document_hash_id}")


async def process_document_with_ai(gcs_uri: str, mime_type: str = "application/pdf") -> dict:
    """
    Process a document using Google Cloud Document AI.
    
    Args:
        gcs_uri: GCS URI of the document (e.g., gs://bucket/path/to/file.pdf)
        mime_type: MIME type of the document (default: application/pdf)
    
    Returns:
        Dictionary containing extracted invoice data with entities
    """
    logger.info(f"Processing document: {gcs_uri}")
    
    # Get configuration from environment
    processor_name = os.environ.get("DOCUMENT_AI_PROCESSOR_NAME")
    
    if not processor_name:
        raise ValueError("DOCUMENT_AI_PROCESSOR_NAME environment variable not set")
    
    
    def process_document():
        """Synchronous function to process document"""
        # Set the API endpoint to match the processor location
        # Extract location from processor_name (format: projects/{project}/locations/{location}/processors/{processor})
        location_from_name = processor_name.split('/')[3] if '/' in processor_name else location
        opts = ClientOptions(api_endpoint=f"{location_from_name}-documentai.googleapis.com")
        
        # Initialize Document AI client with regional endpoint
        if credentials:
            client = documentai.DocumentProcessorServiceClient(
                credentials=credentials,
                client_options=opts
            )
        else:
            client = documentai.DocumentProcessorServiceClient(
                client_options=opts
            )
        
        # Create GCS document
        gcs_document = documentai.GcsDocument(
            gcs_uri=gcs_uri,
            mime_type=mime_type
        )
        
        # Create process request
        request = documentai.ProcessRequest(
            name=processor_name,
            gcs_document=gcs_document
        )
        
        # Process document
        result = client.process_document(request=request)
        return result.document
    
    # Run in thread pool for async operation
    document = await asyncio.to_thread(process_document)
    
    logger.info(f"Document processed successfully: {gcs_uri}")
    
    # Extract structured data
    extracted_data = {
        "text": document.text,
        "entities": [],
        "gcs_uri": gcs_uri
    }
    
    # Parse entities from invoice processor
    for entity in document.entities:
        
        print("entity_start")
        print(entity)
        print("entity_end")

        entity_data = {
            "type": entity.type_,
            "mention_text": entity.mention_text,
            "confidence": entity.confidence,
        }
        
        # Add normalized value if available
        if entity.normalized_value:
            entity_data["normalized_value"] = {
                "text": entity.normalized_value.text,
            }
   
            # Add date value if present
            if entity.normalized_value.date_value:
                entity_data["normalized_value"]["date"] = {
                    "year": entity.normalized_value.date_value.year,
                    "month": entity.normalized_value.date_value.month,
                    "day": entity.normalized_value.date_value.day,
                }

            if entity.normalized_value.float_value:
                entity_data["normalized_value"]["float_value"] = entity.normalized_value.float_value
        
        extracted_data["entities"].append(entity_data)
    
    logger.info(f"Extracted {len(extracted_data['entities'])} entities from document")
    
    return extracted_data

async def list_processors_sample(project_id: str, location: str) -> None:
    # You must set the api_endpoint if you use a location other than 'us'.
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # The full resource name of the location
    # e.g.: projects/project_id/locations/location
    parent = client.common_location_path(project_id, location)
    def make_request():
        return client.list_processors(parent=parent)
    # Make ListProcessors request
    processor_list = await asyncio.to_thread(make_request)

    # Print the processor information
    for processor in processor_list:
        print(f"Processor Name: {processor.name}")
        print(f"Processor Display Name: {processor.display_name}")
        print(f"Processor Type: {processor.type_}")
        print("")


async def copy_blob(bucket_name: str, source_blob_name: str, destination_blob_name: str) -> None:
    """
    Copies a blob from one location to another within the same bucket.
    
    Args:
        bucket_name: Name of the GCS bucket
        source_blob_name: Name of the source blob
        destination_blob_name: Name of the destination blob
    """
    logger.info(f"Copying blob {source_blob_name} to {destination_blob_name} in bucket {bucket_name}")

    def _copy():
        if credentials:
            storage_client = storage.Client(credentials=credentials, project=project_id)
        else:
            storage_client = storage.Client(project=project_id)

        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(source_blob_name)
        
        source_bucket.copy_blob(
            source_blob, source_bucket, destination_blob_name
        )

    await asyncio.to_thread(_copy)
    
    logger.info(f"Successfully copied blob {source_blob_name} to {destination_blob_name}")


def get_blob_name_for_document_uri(document_uri: str) -> str:
    
    document_uri = document_uri.replace("gs://", "").split("/")[1:]

    return "/".join(document_uri)

if __name__ == "__main__":
    # Example usage
    async def main():

        ## First get non-processed documents
        documents = await get_unprocessed_documents()

        for document in documents:

            document_hash_id = document["hashID"]

            gcs_uri = document["gcsUri"]

            if await accounting_info_exists_by_document_hash_id(document_hash_id):

                logger.info(f"Accounting info for document_hash_id {document_hash_id} already exists")

                continue

            result = await process_document_with_ai(gcs_uri)
          
            await write_accounting_info(result, gcs_uri, document_hash_id, document["fromEmailAddressName"])


            await mark_document_as_processed(document_hash_id)

            await copy_blob(
                bucket_name=os.environ.get("GCS_BUCKET_NAME"),
                source_blob_name=get_blob_name_for_document_uri(document["gcsUri"]),
                destination_blob_name=f"processed/{document['fromEmailAddressName']}/{document['attachmentName']}"
            )

    asyncio.run(main())
