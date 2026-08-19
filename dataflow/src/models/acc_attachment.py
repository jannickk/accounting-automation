import hashlib
from typing import Optional
from datetime import datetime
from pydantic import AliasChoices, ConfigDict, Field, computed_field
from PowerPlatform.Dataverse.client import DataverseClient

from .entity_base import EntityBase
from .acc_email import Email


class Attachment(EntityBase):

    model_config = ConfigDict(extra="ignore")

    entity_logical_name: str = Field(exclude=True, default="acc_attachment")
    conent_bytes: Optional[bytes] = Field(default=None, exclude=True)

    acc_emailId: str = Field(
        ...,
        foreign_key="acc_email.acc_emailId",
        validation_alias=AliasChoices("acc_emailId", "acc_emailid"),
    )
    
    acc_isduplicateof: Optional[Email] = Field(default=None, foreign_key="acc_attachment.acc_attachmentId")
    acc_hashid: str = Field(max_length=200)
    acc_processeddocumentai: bool = False
    acc_processeddatetime: Optional[datetime] = None
    acc_attachmentname: str = Field(max_length=500)
    acc_attachmenttype: str = Field(max_length=200)
    acc_storageaccounturi: str = Field(max_length=1000)
    acc_blobname: str = Field(max_length=1000)
    acc_uploadedtodatev: bool = False
    acc_uploadeddatetime: Optional[datetime] = None
    
     # System-generated Unique Identifier for the Attachment record in Dataverse
    acc_attachmentId: str | None = Field(
        default=None,
        primary_key=True,
        default_factory=None,
        validation_alias=AliasChoices("acc_attachmentId", "acc_attachmentid"),
    )


    @computed_field
    def acc_attachment_alternatekey(self) -> str:
        return hashlib.sha256((self.acc_emailId + self.acc_attachmentname).encode('utf-8')).hexdigest()

    def convert_to_odata_payload(self) -> dict:
        """
        Convert the Attachment instance to a dictionary suitable for OData payload.
        This method excludes the 'entity_logical_name' field, includes the computed
        alternate key, and converts lookup fields into the OData bind format.
        """
        record = self.model_dump(mode="json", exclude={"entity_logical_name","conent_bytes"}, exclude_none=True)
        record["acc_attachment_alternatekey"] = self.acc_attachment_alternatekey

        def extract_lookup_id(value, target_pk):
            if isinstance(value, str):
                return value
            if isinstance(value, BaseModel):
                return extract_lookup_id(value.model_dump(mode="json"), target_pk)
            if isinstance(value, dict):
                candidates = [target_pk, target_pk.lower(), target_pk.rstrip("Id"), "id"]
                for key in candidates:
                    if key in value and isinstance(value[key], str):
                        return value[key]
            return None

        payload = {}
        
        for field_name, field_value in record.items():
            field_info = self.model_fields.get(field_name)
            foreign_key = getattr(field_info, "extra", {}).get("foreign_key") if field_info else None
            if foreign_key and field_value is not None:
                target_entity, target_pk = foreign_key.split(".", 1)
                lookup_id = extract_lookup_id(field_value, target_pk)
                if lookup_id:
                    binding_collection = target_entity if target_entity.endswith("s") else f"{target_entity}s"
                    payload[f"{field_name}@odata.bind"] = f"/{binding_collection}({lookup_id})"
                    continue
            payload[field_name] = field_value

        return payload


    def upsert_to_dataverse(self, client: DataverseClient)->Optional["Attachment"]:
        """
        Upsert the attachment record to Dataverse using the provided Dataverse client.

        Performs an upsert (create or update) using the alternate key
        ``acc_attachment_alternatekey``. The record payload is JSON-serialised
        (``mode="json"``) so that datetimes become ISO 8601 strings the
        OData layer can send.
        """

        record = self.model_dump(mode="json", exclude={"entity_logical_name","content_bytes"})
        # Ensure the alternate key value is present for the upsert URL
        record["acc_attachment_alternatekey"] = self.acc_attachment_alternatekey

        client.records.upsert(
            self.entity_logical_name,
            [
                {
                    "alternate_key": {"acc_attachment_alternatekey": self.acc_attachment_alternatekey},
                    "record": self.convert_to_odata_payload(),
                }
            ],
        )
        # returns a new instance
        return AttachmentFactory.fetch_by_alternate_key(client,self.acc_attachment_alternatekey)


class AttachmentFactory:
    @staticmethod
    def create_attachment(
        email: Email,
        hash_id: str,
        attachment_name: str,
        attachment_type: str,
        storage_uri: str,
        blob_name: str,
        is_duplicate_of: Optional[str] = None,

    ) -> "Attachment":
        
        return Attachment(
            acc_emailId=email.acc_emailId,
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

    @staticmethod
    def fetch_by_alternate_key(client: DataverseClient, alternate_key: str) -> Optional[Attachment]:
        """Fetch an `acc_attachment` by its alternate key from Dataverse.

        Returns an `Attachment` instance when found, otherwise `None`.
        """
        # Build simple OData filter using the alternate key column
        filter_str = f"acc_attachment_alternatekey eq '{alternate_key}'"
        result = client.records.list("acc_attachment", filter=filter_str, top=1)
        record = result.first()
        if record is None:
            return None
        data = record.to_dict()
        # Use pydantic model validation to construct Attachment (parses datetimes)

        print(f"Fetched attachment record from Dataverse: {data}")

        return Attachment.model_validate(data)