from typing import Optional
from decimal import Decimal
from datetime import date
from enum import IntEnum
from pydantic import BaseModel


class DocumentType(IntEnum):
    Invoice = 1
    CreditorNote = 2


class Document(BaseModel):
    acc_supplier: str
    acc_attachment: str
    acc_document_type: DocumentType
    acc_document_hash_id: str
    acc_net_amount: Optional[Decimal] = None
    acc_vat_amount: Optional[Decimal] = None
    acc_gross_amount: Optional[Decimal] = None
    acc_invoice_id: Optional[str] = None
    acc_total_amount: Optional[Decimal] = None
    acc_supplier_tax_id: Optional[str] = None
    acc_transaction_currency: Optional[str] = None
    acc_supplier_iban: Optional[str] = None
    acc_invoice_date: Optional[date] = None
    acc_invoice_year: Optional[int] = None
    acc_invoice_month: Optional[int] = None
    acc_invoice_day: Optional[int] = None
    acc_period_of_service_month: Optional[int] = None
    acc_period_of_service_start_date: Optional[date] = None
    acc_period_of_service_end_date: Optional[date] = None
    acc_supplier_email: Optional[str] = None
    acc_supplier_address: Optional[str] = None
    acc_supplier_name: Optional[str] = None
    acc_supplier_registration: Optional[str] = None
    acc_storageaccounturi: Optional[str] = None
    acc_blobname: Optional[str] = None

    class Config:
        use_enum_values = True
        extra = "forbid"
