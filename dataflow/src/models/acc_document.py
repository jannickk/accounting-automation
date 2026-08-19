import hashlib
from typing import Optional
from decimal import Decimal
from datetime import date
from enum import IntEnum
from pydantic import AliasChoices, ConfigDict, Field, computed_field
from PowerPlatform.Dataverse.client import DataverseClient
from .acc_attachment import Attachment
from .entity_base import EntityBase

class DocumentType(IntEnum):
    Invoice = 1
    CreditorNote = 2
    DebitNote = 3
    ProFormaInvoice = 4


class Document(EntityBase):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    entity_logical_name: str = Field(exclude=True, default="acc_document")

    acc_supplier: str
    acc_attachment: str = Field(..., foreign_key="acc_attachment.acc_attachmentId")

    acc_document_type: DocumentType
    acc_document_hash_id: str = Field(max_length=200)
    acc_invoice_date: Optional[date] = None
    acc_net_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_vat_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_gross_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_invoice_id: Optional[str] = Field(default=None, max_length=250)
    acc_total_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("99000000000"))
    acc_supplier_tax_id: Optional[str] = Field(default=None, max_length=100)
    acc_transaction_currency: Optional[str] = None
    acc_supplier_iban: Optional[str] = Field(default=None, max_length=50)
    acc_invoice_year: Optional[int] = None
    acc_invoice_month: Optional[int] = None
    acc_invoice_day: Optional[int] = None
    acc_period_of_service_month: Optional[int] = None
    acc_period_of_service_start_date: Optional[date] = None
    acc_period_of_service_end_date: Optional[date] = None
    acc_supplier_email: Optional[str] = Field(default=None, max_length=320)
    acc_supplier_address: Optional[str] = Field(default=None, max_length=4000)
    acc_supplier_name: Optional[str] = Field(default=None, max_length=250)
    acc_supplier_registration: Optional[str] = Field(default=None, max_length=250)
    acc_storageaccounturi: Optional[str] = Field(default=None, max_length=1000)
    acc_blobname: Optional[str] = Field(default=None, max_length=1000)

     # System-generated Unique Identifier for the Document record in Dataverse
    acc_documentId: str | None = Field(
        default=None,
        primary_key=True,
        default_factory=None,
        validation_alias=AliasChoices("acc_documentId", "acc_documentid"),
    )

    @computed_field
    def acc_document_alternatekey(self) -> str:
        return hashlib.sha256((self.acc_supplier + str(self.acc_invoice_date)).encode('utf-8')).hexdigest()

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
                    "record": record,
                }
            ],
        )