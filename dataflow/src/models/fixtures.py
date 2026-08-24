from datetime import datetime
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from azure.identity import ClientSecretCredential
from config.config import Config
import pytest
import pytest_asyncio
from .entity_base import EntityBase
from PowerPlatform.Dataverse.client import DataverseClient
from .acc_email import Email, EmailFactory
from uuid import uuid4
from typing import Generator
from dotenv import load_dotenv



@pytest.fixture
def config():

    config = Config()

    yield config

@pytest.fixture
def client(config):

    tenant_id = config.DATAVERSE_TENANT_ID
    client_id = config.DATAVERSE_CLIENT_ID
    client_secret = config.DATAVERSE_CLIENT_SECRET
    environment_url = config.DATAVERSE_ENVIRONMENT_URL

    if not all([tenant_id, client_id, client_secret, environment_url]):
        raise ValueError("Missing required Dataverse environment variables.")

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)

    yield DataverseClient(environment_url, credential)



@pytest.fixture
def client(config):

    tenant_id = config.DATAVERSE_TENANT_ID
    client_id = config.DATAVERSE_CLIENT_ID
    client_secret = config.DATAVERSE_CLIENT_SECRET
    environment_url = config.DATAVERSE_ENVIRONMENT_URL

    if not all([tenant_id, client_id, client_secret, environment_url]):
        raise ValueError("Missing required Dataverse environment variables.")

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)

    yield DataverseClient(environment_url, credential)



    
@pytest.fixture
def email():

    sample = {
        "id": "msg-1",
        "subject": "Test",
        "numAttachments": 0,
        "acc_outlook_emailid": "msg-1",
        "receivedDateTime": "2026-08-07T12:00:00Z",
        "body": {"content": "hello world", "contentType": "text"},
        "sender": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
    }

    yield  EmailFactory.create_email(sample)



@pytest.fixture
def email_with_id() -> Generator[Email, None, None]:
    sample_email = {
        "id": "msg-1",
        "subject": "Test",
        "numAttachments": 0,
        "receivedDateTime": "2026-08-07T12:00:00Z",
        "body": {"content": "hello world", "contentType": "text"},
        "sender": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
    }

    
    email = EmailFactory.create_email(sample_email)

    email.acc_emailId = uuid4().hex  # Simulate a Dataverse-generated email ID

    yield email

@pytest.fixture
def email_in_dataverse(client: DataverseClient, email: Email):
    """
    Upsert the email record to Dataverse using the provided Dataverse client.

     Performs an upsert using the alternate key
    """


    yield email.upsert_to_dataverse(client)  # Ensure the email is upserted to Dataverse