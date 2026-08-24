import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os
from main import process_document_with_ai, get_unprocessed_emails, get_email_attachments, write_accounting_info


@pytest.mark.asyncio
@patch("main.documentai.DocumentProcessorServiceClient")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_process_document_with_ai_success(mock_to_thread, mock_client_class):
    """Test successful document processing"""
    
    # Setup mock document with entities
    mock_entity = MagicMock()
    mock_entity.type_ = "invoice_number"
    mock_entity.mention_text = "INV-12345"
    mock_entity.confidence = 0.95
    mock_entity.normalized_value = None
    
    mock_document = MagicMock()
    mock_document.text = "Sample invoice text"
    mock_document.entities = [mock_entity]
    
    # Mock the to_thread to return our mock document
    mock_to_thread.return_value = mock_document
    
    # Test data
    gcs_uri = "gs://test-bucket/invoice.pdf"
    
    # Set environment variables
    with patch.dict(os.environ, {
        "DOCUMENT_AI_PROCESSOR_ID": "test-processor-id",
        "DOCUMENT_AI_LOCATION": "eu",
        "GCP_PROJECT_ID": "test-project"
    }):
        result = await process_document_with_ai(gcs_uri)
    
    # Assertions
    assert result["gcs_uri"] == gcs_uri
    assert result["text"] == "Sample invoice text"
    assert len(result["entities"]) == 1
    assert result["entities"][0]["type"] == "invoice_number"
    assert result["entities"][0]["mention_text"] == "INV-12345"
    assert result["entities"][0]["confidence"] == 0.95
    
    # Verify to_thread was called
    mock_to_thread.assert_awaited_once()


@pytest.mark.asyncio
@patch("main.documentai.DocumentProcessorServiceClient")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_process_document_with_money_entity(mock_to_thread, mock_client_class):
    """Test processing document with money entity"""
    
    # Setup mock money value
    mock_money = MagicMock()
    mock_money.currency_code = "EUR"
    mock_money.units = 100
    mock_money.nanos = 500000000
    
    mock_normalized = MagicMock()
    mock_normalized.text = "100.50 EUR"
    mock_normalized.money_value = mock_money
    mock_normalized.date_value = None
    
    mock_entity = MagicMock()
    mock_entity.type_ = "total_amount"
    mock_entity.mention_text = "€100.50"
    mock_entity.confidence = 0.98
    mock_entity.normalized_value = mock_normalized
    
    mock_document = MagicMock()
    mock_document.text = "Total: €100.50"
    mock_document.entities = [mock_entity]
    
    mock_to_thread.return_value = mock_document
    
    gcs_uri = "gs://test-bucket/invoice.pdf"
    
    with patch.dict(os.environ, {
        "DOCUMENT_AI_PROCESSOR_ID": "test-processor-id",
        "GCP_PROJECT_ID": "test-project"
    }):
        result = await process_document_with_ai(gcs_uri)
    
    # Assertions
    assert len(result["entities"]) == 1
    entity = result["entities"][0]
    assert entity["type"] == "total_amount"
    assert "normalized_value" in entity
    assert entity["normalized_value"]["money"]["currency_code"] == "EUR"
    assert entity["normalized_value"]["money"]["units"] == 100


@pytest.mark.asyncio
async def test_process_document_missing_processor_id():
    """Test error when processor ID is not set"""
    
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="DOCUMENT_AI_PROCESSOR_NAME"):
            await process_document_with_ai("gs://test-bucket/invoice.pdf")


@pytest.mark.asyncio
@patch("main.bq_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_get_unprocessed_emails(mock_to_thread, mock_bq_client):
    """Test retrieving unprocessed emails from BigQuery"""
    
    # Mock email data
    mock_emails = [
        {
            "subject": "Invoice 123",
            "receivedDateTime": "2025-12-27T10:00:00Z",
            "processed": False,
            "hashID": "abc123"
        },
        {
            "subject": "Invoice 456",
            "receivedDateTime": "2025-12-27T11:00:00Z",
            "processed": None,
            "hashID": "def456"
        }
    ]
    
    mock_to_thread.return_value = mock_emails
    
    with patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project",
        "GCP_DATASET_ID": "accounting",
        "GCP_TABLE_ID": "emails"
    }):
        result = await get_unprocessed_emails()
    
    # Assertions
    assert len(result) == 2
    assert result[0]["subject"] == "Invoice 123"
    assert result[1]["subject"] == "Invoice 456"
    mock_to_thread.assert_awaited_once()


@pytest.mark.asyncio
@patch("main.bq_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_get_email_attachments(mock_to_thread, mock_bq_client):
    """Test retrieving attachments for a specific email"""
    
    # Mock attachment data
    mock_attachments = [
        {
            "emailID": "abc123",
            "attachmentName": "invoice.pdf",
            "attachmentType": "application/pdf",
            "gcsUri": "gs://bucket/path/invoice.pdf"
        },
        {
            "emailID": "abc123",
            "attachmentName": "receipt.pdf",
            "attachmentType": "application/pdf",
            "gcsUri": "gs://bucket/path/receipt.pdf"
        }
    ]
    
    mock_to_thread.return_value = mock_attachments
    
    with patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project",
        "GCP_DATASET_ID": "accounting"
    }):
        result = await get_email_attachments("abc123")
    
    # Assertions
    assert len(result) == 2
    assert result[0]["attachmentName"] == "invoice.pdf"
    assert result[0]["gcsUri"] == "gs://bucket/path/invoice.pdf"
    assert result[1]["attachmentName"] == "receipt.pdf"
    mock_to_thread.assert_awaited_once()


@pytest.mark.asyncio
@patch("main.bq_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_write_accounting_info(mock_to_thread, mock_bq_client):
    """Test writing Document AI results to accounting_info table"""
    
    # Mock Document AI result
    document_ai_result = {
        "gcs_uri": "gs://bucket/invoice.pdf",
        "entities": [
            {
                "type": "total_amount",
                "mention_text": "€100.50",
                "confidence": 0.98
            },
            {
                "type": "invoice_id",
                "mention_text": "INV-12345",
                "confidence": 0.95
            },
            {
                "type": "supplier_name",
                "mention_text": "Acme Corp",
                "confidence": 0.92
            },
            {
                "type": "invoice_date",
                "mention_text": "2025-12-27",
                "confidence": 0.90,
                "normalized_value": {
                    "date": {
                        "year": 2025,
                        "month": 12,
                        "day": 27
                    }
                }
            }
        ]
    }
    
    gcs_uri = "gs://bucket/invoice.pdf"
    
    with patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project",
        "GCP_DATASET_ID": "accounting"
    }):
        await write_accounting_info(document_ai_result, gcs_uri)
    
    # Verify to_thread was called
    mock_to_thread.assert_awaited_once()

