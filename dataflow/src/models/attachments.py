from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from PowerPlatform.Dataverse.models import UpsertItem
from PowerPlatform.Dataverse.client import DataverseClient


class Attachment(BaseModel):

    entity_logical_name: str = Field(exclude=True, default="acc_attachment")

    acc_emailid: str
    acc_isduplicateof: Optional[str] = None
    acc_hashid: str
    acc_processeddocumentai: bool = False
    acc_processeddatetime: Optional[datetime] = None
    acc_attachmentname: str
    acc_attachmenttype: str
    acc_storageaccounturi: str
    acc_blobname: str
    acc_uploadedtodatev: bool = False
    acc_uploadeddatetime: Optional[datetime] = None

    class Config:
        extra = "forbid"

    def write_to_dataverse(self, client: DataverseClient):
        """
        Write (upsert) the attachment record to Dataverse using the provided Dataverse client.

        The record is identified by the ``acc_hashid`` alternate key, so re-processing the
        same attachment updates the existing row instead of creating a duplicate. Values are
        JSON-serialised (``mode="json"``) so that datetimes become ISO 8601 strings the
        OData layer can send.
        """

        client.records.upsert(self.entity_logical_name, [
                UpsertItem(
                    alternate_key={"acc_hashid": self.acc_hashid},
                    record=self.model_dump(mode="json", exclude={"entity_logical_name"}),
                ),
            ]
            )


class AttachmentFactory:
    @staticmethod
    def create_attachment(
        email_id: str,
        hash_id: str,
        attachment_name: str,
        attachment_type: str,
        storage_uri: str,
        blob_name: str,
        is_duplicate_of: Optional[str] = None,
    ) -> "Attachment":
        return Attachment(
            acc_emailid=email_id,
            acc_isduplicateof=is_duplicate_of,
            acc_hashid=hash_id,
            acc_processeddocumentai=False,
            acc_processeddatetime=None,
            acc_attachmentname=attachment_name,
            acc_attachmenttype=attachment_type,
            acc_storageaccounturi=storage_uri,
            acc_blobname=blob_name,
            acc_uploadedtodatev=False,
            acc_uploadeddatetime=None,
        )
