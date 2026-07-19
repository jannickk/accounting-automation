import pytest
from unittest.mock import AsyncMock, patch
import os
from main import get_emails, get_email_attachments, upload_to_gcs

@pytest.mark.asyncio
@patch("main.get_access_token", new_callable=AsyncMock)
async def test_get_emails_no_token(mock_get_token):
    mock_get_token.return_value = None
    
    with pytest.raises(Exception, match="Error acquiring access token"):
        await get_emails()

@pytest.mark.asyncio
@patch("main.get_access_token", new_callable=AsyncMock)
@patch("main.get_json_from_url", new_callable=AsyncMock)
async def test_get_emails_success(mock_get_json, mock_get_token):
    mock_get_token.return_value = "fake_token"
    # Mock first page and empty second page to stop recursion
    mock_get_json.side_effect = [
        {"value": [{"subject": "Test Email", "from": {"emailAddress": {"address": "sender@example.com"}}, "receivedDateTime": "2023-10-27T10:00:00Z"}]},
        {"value": []}
    ]
    
    with patch.dict(os.environ, {"SHARED_MAILBOX_EMAIL": "test@example.com"}):
        emails = await get_emails()
        
        assert len(emails) == 1
        assert emails[0]["subject"] == "Test Email"

@pytest.mark.asyncio
@patch("main.get_access_token", new_callable=AsyncMock)
@patch("main.get_json_from_url", new_callable=AsyncMock)
async def test_get_email_attachments(mock_get_json, mock_get_token):
    mock_get_token.return_value = "fake_token"
    mock_get_json.return_value = {"value": [{"id": "att1", "name": "file.txt"}]}
    
    with patch.dict(os.environ, {"SHARED_MAILBOX_EMAIL": "test@example.com"}):
        attachments = await get_email_attachments("email_id_123")
        
        assert len(attachments) == 1
        assert attachments[0]["name"] == "file.txt"
        
        # Verify calls
        mock_get_json.assert_called_once()
        args, kwargs = mock_get_json.call_args
        assert "/messages/email_id_123/attachments" in args[0]

@pytest.mark.asyncio
@patch("main.storage.Client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_upload_to_gcs(mock_to_thread, mock_storage_client):
    # Setup mocks
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    
    # Test data
    test_data = "SGVsbG8gV29ybGQh"  # "Hello World!" in base64
    bucket_name = "test-bucket"
    object_name = "test-file.txt"
    
    # Call function
    result = await upload_to_gcs(test_data, bucket_name, object_name)
    
    # Assertions
    assert result == f"gs://{bucket_name}/{object_name}"
    mock_storage_client.return_value.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(object_name)
    mock_to_thread.assert_awaited_once()
