import hashlib
from typing import Optional
from decimal import Decimal
from datetime import date
from pydantic import AliasChoices, ConfigDict, Field, computed_field
from PowerPlatform.Dataverse.client import DataverseClient
from .acc_attachment import Attachment
from .entity_base import EntityBase


class Document(EntityBase):

    model_config = ConfigDict(extra="ignore")

    entity_logical_name: str = Field(exclude=True, default="acc_document")

    acc_creditorId: str = Field(
                                    ..., 
                                    foreign_key="acc_creditor.acc_creditorId",
                                    validation_alias=AliasChoices("acc_creditorId", "acc_creditorid", "_acc_creditorid_value")
                                )
    acc_attachmentId: str = Field(
                                    ..., 
                                    foreign_key="acc_attachment.acc_attachmentId",
                                    validation_alias=AliasChoices("acc_attachmentId", "acc_attachmentid", "_acc_attachmentid_value")
                                )

    acc_invoice_date: Optional[date] = None
    acc_net_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_vat_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_gross_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_invoice_id: Optional[str] = Field(default=None, max_length=250)
    acc_total_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_supplier_tax_id: Optional[str] = Field(default=None, max_length=100)
    acc_transactioncurrencyId: str = Field(
                                                ...,
                                                foreign_key="transactioncurrency.transactioncurrencyid",
                                                validation_alias=AliasChoices("acc_transactioncurrencyId", "acc_transactioncurrencyid", "_acc_transactioncurrencyid_value")
                                        )
    acc_supplier_iban: Optional[str] = Field(default=None, max_length=50)
    acc_invoice_year: Optional[int] = None
    acc_invoice_month: Optional[int] = None
    acc_products_and_services_received: Optional[str] = None
    acc_invoice_day: Optional[int] = None
    acc_period_of_service_month: Optional[int] = None
    acc_period_of_service_start_date: Optional[date] = None
    acc_period_of_service_end_date: Optional[date] = None
    acc_supplier_email: Optional[str] = Field(default=None, max_length=320)
    acc_supplier_address: Optional[str] = Field(default=None, max_length=4000)
    acc_supplier_name: Optional[str] = Field(default=None, max_length=250)
    acc_supplier_registration: Optional[str] = Field(default=None, max_length=250)

     # System-generated Unique Identifier for the Document record in Dataverse
    acc_documentId: str | None = Field(
        default=None,
        primary_key=True,
        default_factory=None,
        validation_alias=AliasChoices("acc_documentId", "acc_documentid"),
    )

    @computed_field
    def acc_document_alternatekey(self) -> str:
        return hashlib.sha256((self.acc_creditorId + str(self.acc_invoice_date)).encode('utf-8')).hexdigest()

    def upsert_to_dataverse(self, client: DataverseClient):
        """
        Upsert the document record to Dataverse using the provided Dataverse client.

        Performs an upsert (create or update) using the alternate key
        ``acc_document_alternatekey``. The record payload is JSON-serialised
        (``mode="json"``) so that datetimes become ISO 8601 strings the
        OData layer can send.
        """

        record = self.model_dump(mode="json", exclude={"entity_logical_name"})
        # Ensure the alternate key value is present for the upsert URL
        record["acc_document_alternatekey"] = self.acc_document_alternatekey

        client.records.upsert(
            self.entity_logical_name,
            [
                {
                    "alternate_key": {"acc_document_alternatekey": self.acc_document_alternatekey},
                    "record": self.convert_to_odata_payload(),
                }
            ],
        )

    def convert_to_odata_payload(self)->dict:

        record = self.model_dump(mode="json", exclude={"entity_logical_name"}, exclude_none=True)

        record["acc_document_alternatekey"] = self.acc_document_alternatekey

        payload = {}
        
        for field_name, field_value in record.items():

            field_info = Document.model_fields.get(field_name)

            json_extra_schema = getattr(field_info, "json_schema_extra", {})

            if json_extra_schema is not None:

                foreign_key = json_extra_schema.get("foreign_key",None) if field_info else None

                if foreign_key and field_value is not None:

                    # acc_email.acc_emailId
                    target_entity, target_pk = foreign_key.split(".", 1)

                    # this is the Id of 
                    lookup_id = field_value

                    if lookup_id:
                        binding_collection = target_entity if target_entity.endswith("s") else f"{target_entity}s"
                        payload[f"{field_name}@odata.bind"] = f"/{binding_collection}({lookup_id})"
                        continue
            payload[field_name] = field_value

        return payload

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