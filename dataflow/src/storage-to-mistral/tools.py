from enum import Enum, IntEnum
from pydantic import BaseModel
from typing import Annotated
from annotated_types import Gt

class PeriodOfService(BaseModel):

   start_date: str
   end_date: str

class CurrenciesEnum(str, Enum):

    euro = 'EUR'
    USDollar = 'USD'

class ProductOrService(BaseModel):
    
    product_service: str
    details: str

class DocumentData(BaseModel):
    creditor: str
    date_of_invoice: str
    period_of_service: PeriodOfService
    debitor: str
    total_amount: str
    total_amount_of_taxes_paid: Annotated[float, Gt(0)]
    invoice_number: str
    products_services_received: list[ProductOrService]
    transaction_currency: CurrenciesEnum



print(DocumentData.model_json_schema())