from typing import Optional
from datetime import datetime
from pydantic import AliasChoices, ConfigDict, Field, model_validator, BaseModel
import hashlib
from PowerPlatform.Dataverse.client import DataverseClient

from .entity_base import EntityBase


class Email(EntityBase):
    model_config = ConfigDict(extra="ignore")

    entity_logical_name: str = Field(exclude=True, default="acc_email")


    acc_outlook_emailid: str = Field(max_length=200)
    acc_duplicate_emailid: Optional[str] = Field(
        default=None,
        foreign_key="acc_email.acc_emailId",
        validation_alias=AliasChoices("acc_duplicate_emailId", "acc_duplicate_emailid","_acc_duplicate_emailid_value")
    )
    acc_subject: Optional[str] = Field(default=None, max_length=500)
    acc_numofattachments: Optional[int] = None
    acc_receiveddatetime: datetime
    acc_receiveddatetime_year: int
    acc_receiveddatetime_month: int
    acc_ingesteddatetime: datetime
    acc_processeddatetime: datetime
    acc_hashid: str = Field(max_length=200)
    acc_email_alternatekey: Optional[str] = Field(default=None, max_length=200)
    acc_sender_name: Optional[str] = Field(default=None, max_length=250)
    acc_sender_address: Optional[str] = Field(default=None, max_length=320)
    acc_from_name: Optional[str] = Field(default=None, max_length=250)
    acc_from_address: Optional[str] = Field(default=None, max_length=320)
    acc_torecipients_json: Optional[str] = Field(default=None, max_length=4000)
    acc_body_contenttype: Optional[str] = Field(default=None, max_length=100)
    acc_body_contentbytes_b64: Optional[str] = Field(default=None, max_length=4000)
    acc_sender_json: Optional[str] = Field(default=None, max_length=4000)

    # System-generated Unique Identifier for the Email record in Dataverse
    acc_emailId: str | None = Field(
        default=None,
        primary_key=True,
        default_factory=None,
        validation_alias=AliasChoices("acc_emailId", "acc_emailid"),
    )

    @model_validator(mode="after")
    def compute_alternate_key(self) -> "Email":
        if not self.acc_email_alternatekey and self.acc_sender_address and self.acc_receiveddatetime:
            self.acc_email_alternatekey = hashlib.sha256((self.acc_sender_address + str(self.acc_receiveddatetime)).encode("utf-8")
            ).hexdigest()
        return self


    def upsert_to_dataverse(self, client: DataverseClient) -> "Email":
        """
        Upsert the email record to Dataverse using the provided Dataverse client.

        Performs an upsert (create or update) using the alternate key
        ``acc_email_alternatekey``. The record payload is JSON-serialised
        (``mode="json"``) so that datetimes become ISO 8601 strings the
        OData layer can send.
        """

        # Build an OData-compatible payload that converts lookup fields
        # into the `@odata.bind` form so Dataverse receives GUIDs/links
        record = self.convert_to_odata_payload()
        client.records.upsert(
            self.entity_logical_name,
            [
                {
                    "alternate_key": {"acc_email_alternatekey": self.acc_email_alternatekey},
                    "record": record,
                }
            ],
        )

        print(f"Upserted email record with alternate key: {self.acc_email_alternatekey}")

        return EmailFactory.fetch_by_alternate_key(client, self.acc_email_alternatekey)


    def convert_to_odata_payload(self) -> dict:
        """
        Convert the Attachment instance to a dictionary suitable for OData payload.
        This method excludes the 'entity_logical_name' field, includes the computed
        alternate key, and converts lookup fields into the OData bind format.
        """
        record = self.model_dump(mode="json", exclude={"entity_logical_name","conent_bytes"}, exclude_none=True)

        ## the record will have the serialization_aliases

        record["acc_email_alternatekey"] = self.acc_email_alternatekey

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

            field_info = Email.model_fields.get(field_name)

            json_extra_schema = getattr(field_info, "json_schema_extra", {})

            if json_extra_schema is not None:

                foreign_key = json_extra_schema.get("foreign_key",None) if field_info else None

                if foreign_key and field_value is not None:

                    # acc_email.acc_emailId
                    target_entity, target_pk = foreign_key.split(".", 1)

                    # this would be target_pk
                    lookup_id = extract_lookup_id(field_value, target_pk)

                    if lookup_id:
                        binding_collection = target_entity if target_entity.endswith("s") else f"{target_entity}s"
                        payload[f"{field_name}@odata.bind"] = f"/{binding_collection}({lookup_id})"
                        continue
            payload[field_name] = field_value

        return payload



class EmailFactory:
    @staticmethod
    def create_email(email: dict) -> Email:
        return Email(
            acc_outlook_emailid=email.get("id"),
            acc_duplicate_emailid=email.get("_acc_duplicate_emailid_value") or email.get("acc_duplicate_emailid"),
            acc_subject=email.get("subject"),
            acc_numofattachments=email.get("numAttachments"),
            acc_receiveddatetime=datetime.fromisoformat(email.get("receivedDateTime").replace("Z", "+00:00")),
            acc_receiveddatetime_year=datetime.fromisoformat(email.get("receivedDateTime").replace("Z", "+00:00")).year,
            acc_receiveddatetime_month=datetime.fromisoformat(email.get("receivedDateTime").replace("Z", "+00:00")).month,
            acc_ingesteddatetime=datetime.utcnow(),
            acc_processeddatetime=datetime.utcnow(),
            acc_hashid=hashlib.sha256(email.get("body").get("content").encode()).hexdigest(),
            acc_sender_name=email.get("sender").get("emailAddress").get("name") if email.get("sender") else None,
            acc_sender_address=email.get("sender").get("emailAddress").get("address") if email.get("sender") else None,
            acc_from_name=email.get("from").get("emailAddress").get("name") if email.get("from") else None,
            acc_from_address=email.get("from").get("emailAddress").get("address") if email.get("from") else None,
            acc_torecipients_json=str(email.get("toRecipients")) if email.get("toRecipients") else None,
            acc_body_contenttype=email.get("body").get("contentType") if email.get("body") else None,
            acc_body_contentbytes_b64=email.get("body").get("contentBytes") if email.get("body") else None,
            acc_sender_json=str(email.get("sender")) if email.get("sender") else None
        )

    @staticmethod
    def fetch_by_alternate_key(client: DataverseClient, alternate_key: str) -> Optional[Email]:
        """Fetch an `acc_email` by its alternate key from Dataverse.

        Returns an `Email` instance when found, otherwise `None`.
        """
        # Build simple OData filter using the alternate key column
        filter_str = f"acc_email_alternatekey eq '{alternate_key}'"
        result = client.records.list("acc_email", filter=filter_str, top=1)
        record = result.first()
        if record is None:
            raise Exception(f"Record with alternate key {alternate_key} does not exist")
        data = record.to_dict()
        # Use pydantic model validation to construct Email (parses datetimes)


        return Email.model_validate(data)