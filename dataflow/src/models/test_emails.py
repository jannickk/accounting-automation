from datetime import datetime
import hashlib

from azure.identity import ClientSecretCredential
from config.config import Config
import pytest
from .entity_base import EntityBase
from PowerPlatform.Dataverse.client import DataverseClient

from .acc_email import Email, EmailFactory

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
def email_in_dataverse(client: DataverseClient, email: Email):
    """
    Upsert the email record to Dataverse using the provided Dataverse client.

     Performs an upsert (create or update) using the alternate key
    ``acc_email_alternatekey``. The record payload is JSON-serialised
     (``mode="json"``) so that datetimes become ISO 8601 strings the
     OData layer can send.
    """

    record = email.convert_to_odata_payload()

    print(f"Upserting email record with alternate key: {record}")

    client.records.upsert(
            email.entity_logical_name,
            [
                {
                    "alternate_key": {"acc_email_alternatekey": email.acc_email_alternatekey},
                    "record": record,
                }
            ],
        )

    yield email


    
def test_fetch_email_by_alternate_key(client, email_in_dataverse):
    """
    Test fetching an email by its alternate key from Dataverse.
    """

    # Fetch the email by its alternate key
    fetched_email = EmailFactory.fetch_by_alternate_key(client, email_in_dataverse.acc_email_alternatekey)

    assert fetched_email is not None
    assert fetched_email.acc_outlook_emailid == email_in_dataverse.acc_outlook_emailid
    assert fetched_email.acc_subject == email_in_dataverse.acc_subject


def test_email_computed_alternate_key_matches_manual_hash():
    # Build a sample email payload similar to Microsoft Graph shape
    received = datetime.fromisoformat("2026-08-07T12:00:00+00:00")
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

    email = EmailFactory.create_email(sample)

    # computed field should equal sha256(sender_address + receiveddatetime)
    expected = hashlib.sha256((email.acc_sender_address + str(email.acc_receiveddatetime)).encode("utf-8")).hexdigest()
    assert email.acc_email_alternatekey == expected


def test_email_model_validate_accepts_dataverse_payload():
    payload = {
        "acc_emailid": "ecb30fd1-1e94-f111-8076-7ced8d2ca142",
        "acc_outlook_emailid": "msg-1",
        "acc_subject": "Dataverse payload test",
        "acc_numofattachments": 0,
        "acc_receiveddatetime": "2026-08-07T12:00:00+00:00",
        "acc_receiveddatetime_year": 2026,
        "acc_receiveddatetime_month": 8,
        "acc_ingesteddatetime": "2026-08-07T12:00:00+00:00",
        "acc_processeddatetime": "2026-08-07T12:00:00+00:00",
        "acc_hashid": "abc123",
        "acc_email_alternatekey": "alt-key-123",
        "acc_sender_address": "alice@example.com",
        "acc_from_address": "alice@example.com",
        "_owninguser_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_modifiedonbehalfby_value": None,
        "_createdonbehalfby_value": None,
        "_modifiedby_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_owningbusinessunit_value": "5ac5d729-2e30-f111-88b3-6045bddeaf59",
        "_owningteam_value": None,
        "_createdby_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_ownerid_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
    }


 

    email = Email.model_validate(payload)

    print(email.model_dump_json(indent=2))

    assert email.acc_emailId == payload["acc_emailid"]
    assert email.acc_sender_address == "alice@example.com"
    assert email.ownerid_value == payload["_ownerid_value"]


def test_email_convert_to_odata_payload():
    """
    Test that convert_to_odata_payload produces a valid OData payload.
    Validates that:
    - Fields are properly serialized to JSON format
    - Excluded fields are not present
    - None values are excluded
    - The alternate key is included
    - Datetime fields are in ISO 8601 format
    """
    received = datetime.fromisoformat("2026-08-07T12:00:00+00:00")
    sample = {
        "id": "msg-1",
        "subject": "Test Email",
        "numAttachments": 2,
        "acc_outlook_emailid": "msg-1",
        "receivedDateTime": "2026-08-07T12:00:00Z",
        "body": {"content": "hello world", "contentType": "text"},
        "sender": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
    }

    email = EmailFactory.create_email(sample)
    odata_payload = email.convert_to_odata_payload()

    # Validate payload is a dictionary
    assert isinstance(odata_payload, dict)

    # Validate that excluded fields are not present
    assert "entity_logical_name" not in odata_payload
    assert "acc_body_contentbytes_b64" not in odata_payload
    assert "acc_emailId" not in odata_payload

    # Validate that required fields are present
    assert "acc_outlook_emailid" in odata_payload
    assert "acc_subject" in odata_payload
    assert "acc_sender_address" in odata_payload
    assert "acc_email_alternatekey" in odata_payload

    # Validate field values
    assert odata_payload["acc_outlook_emailid"] == "msg-1"
    assert odata_payload["acc_subject"] == "Test Email"
    assert odata_payload["acc_sender_address"] == "alice@example.com"
    assert odata_payload["acc_numofattachments"] == 2

    # Validate datetime serialization (should be ISO 8601 strings)
    assert isinstance(odata_payload["acc_receiveddatetime"], str)
    assert "T" in odata_payload["acc_receiveddatetime"]  # ISO 8601 format check
    assert isinstance(odata_payload["acc_ingesteddatetime"], str)
    assert isinstance(odata_payload["acc_processeddatetime"], str)

    # Validate that None values are excluded
    assert "acc_sender_name" not in odata_payload or odata_payload["acc_sender_name"] is not None
    assert "acc_from_name" not in odata_payload or odata_payload["acc_from_name"] is not None

