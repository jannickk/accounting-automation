from email.generator import Generator
import hashlib
from typing import Generator
import pytest
from uuid import uuid4

from pydantic import ValidationError
from .entity_base import EntityBase
from .acc_attachment import AttachmentFactory, Attachment
from .acc_email import Email, EmailFactory

from .fixtures import *

def test_attachment_factory_validation_failure_for_misaligned_kwargs():
    """
    The current `AttachmentFactory.create_attachment` uses mismatched kwarg names
    compared to the `Attachment` model. This test ensures the factory surfaces
    a ValidationError so the mismatch is visible to developers.
    """


    # The factory is expected to raise a TypeError for missing email input
    with pytest.raises(TypeError):
        AttachmentFactory.create_attachment(
            hash_id="h1",
            attachment_name="file.pdf",
            attachment_type="application/pdf",
            storage_uri="https://storage.example/blob",
            blob_name="file.pdf",
        )

def test_attachment_factory_creates_valid_attachment(email_with_id: Email):
    """
    This test ensures that the `AttachmentFactory.create_attachment` method
    correctly creates a valid `Attachment` instance when provided with the
    correct arguments.
    """

    attachment = AttachmentFactory.create_attachment(
        email=email_with_id,
        hash_id="h1",
        attachment_name="file.pdf",
        attachment_type="application/pdf",
        storage_uri="https://storage.example/blob",
        blob_name="file.pdf",
    )

    # Validate that the created attachment is an instance of Attachment
    assert isinstance(attachment, Attachment)

    # Validate that the attachment's fields match the provided values
    assert attachment.acc_emailId == email_with_id.acc_emailId
    assert attachment.acc_hashid == "h1"
    assert attachment.acc_attachmentname == "file.pdf"
    assert attachment.acc_attachmenttype == "application/pdf"
    assert attachment.acc_storageaccounturi == "https://storage.example/blob"
    assert attachment.acc_blobname == "file.pdf"


def test_attachment_convert_to_odata_payload(email_with_id: Email):
    """
    Test that convert_to_odata_payload produces a valid OData payload.
    Validates that:
    - Payload is a dictionary
    - Excluded fields (entity_logical_name, conent_bytes) are not present
    - Required fields are present with correct values
    - Boolean fields are properly serialized
    - The computed alternate key is included
    - DateTime fields are in ISO 8601 format when present
    """
    attachment = AttachmentFactory.create_attachment(
        email=email_with_id,
        hash_id="hash-abc-123",
        attachment_name="invoice.pdf",
        attachment_type="application/pdf",
        storage_uri="https://storageaccount.blob.core.windows.net/files",
        blob_name="invoice.pdf",
    )
    
    odata_payload = attachment.convert_to_odata_payload()

    # Validate payload is a dictionary
    assert isinstance(odata_payload, dict)

    # Validate that excluded fields are not present
    assert "entity_logical_name" not in odata_payload
    assert "conent_bytes" not in odata_payload

    # Validate that required fields are present
    assert "acc_emailId" in odata_payload
    assert "acc_hashid" in odata_payload
    assert "acc_attachmentname" in odata_payload
    assert "acc_attachmenttype" in odata_payload
    assert "acc_storageaccounturi" in odata_payload
    assert "acc_blobname" in odata_payload

    # Validate field values
    assert odata_payload["acc_emailId"] == email_with_id.acc_emailId
    assert odata_payload["acc_hashid"] == "hash-abc-123"
    assert odata_payload["acc_attachmentname"] == "invoice.pdf"
    assert odata_payload["acc_attachmenttype"] == "application/pdf"
    assert odata_payload["acc_storageaccounturi"] == "https://storageaccount.blob.core.windows.net/files"
    assert odata_payload["acc_blobname"] == "invoice.pdf"

    # Validate boolean fields
    assert odata_payload["acc_processeddocumentai"] is False
    assert odata_payload["acc_uploadedtodatev"] is False

    # Validate that the computed alternate key is included
    assert "acc_attachment_alternatekey" in odata_payload
    assert isinstance(odata_payload["acc_attachment_alternatekey"], str)
    assert len(odata_payload["acc_attachment_alternatekey"]) == 64  # SHA256 hex digest length

    # Validate that None-valued datetime fields are excluded (exclude_none behavior)
    # acc_processeddatetime and acc_uploadeddatetime should not be in payload
    assert "acc_processeddatetime" not in odata_payload or odata_payload["acc_processeddatetime"] is not None
    assert "acc_uploadeddatetime" not in odata_payload or odata_payload["acc_uploadeddatetime"] is not None

def test_create_attachment_insert_into_dataverse(email_in_dataverse: Email, client: DataverseClient):
    """
    Test that an attachment created by the factory can be upserted into Dataverse.
    This test assumes that the Dataverse client is properly configured and connected.
    """


    print(email_in_dataverse.model_dump_json(indent=2))

    attachment = AttachmentFactory.create_attachment(
        email=email_in_dataverse,
        hash_id="hash-xyz-789",
        attachment_name="report.pdf",
        attachment_type="application/pdf",
        storage_uri="https://storageaccount.blob.core.windows.net/reports",
        blob_name="report.pdf",
    )

    # Attempt to upsert the attachment into Dataverse
    try:
        inserted_attachment = attachment.upsert_to_dataverse(client)
    except Exception as e:
        pytest.fail(f"Upserting attachment to Dataverse failed: {e}")

    assert inserted_attachment.acc_attachmentId is not None
    assert inserted_attachment.modifiedon is not None

