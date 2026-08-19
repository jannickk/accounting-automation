import pytest
from unittest.mock import AsyncMock, Mock, patch
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import Email
from models.fixtures import *
from PowerPlatform.Dataverse.client import DataverseClient
from main import get_emails_from_inbox, get_email_attachments_from_inbox, get_email_by_alternate_key_dataverse

@pytest.mark.asyncio
@patch("main.get_access_token", new_callable=AsyncMock)
async def test_get_emails_no_token(mock_get_token):
    mock_get_token.return_value = None
    
    with pytest.raises(Exception, match="Error acquiring access token"):
        await get_emails_from_inbox(config)


@pytest.mark.asyncio
async def test_get_email_by_alternate_key_dataverse(email_in_dataverse: Email, client: DataverseClient):
    

    result = await get_email_by_alternate_key_dataverse(email_in_dataverse.acc_email_alternatekey, client)

    assert result is not None
    assert result.acc_emailId == email_in_dataverse.acc_emailId


@pytest.mark.asyncio
async def test_get_email_by_alternate_key_dataverse(email_in_dataverse: Email, client: DataverseClient):
    

    result = await get_email_by_alternate_key_dataverse(hashlib.sha256("Some Other key".encode()).hexdigest(), client)

    assert result is None
