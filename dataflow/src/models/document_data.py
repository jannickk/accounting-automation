from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from enum import Enum, IntEnum
from pydantic import BaseModel
from typing import Annotated
from annotated_types import Gt, Ge


class PeriodOfService(BaseModel):

   start_date: str | None
   end_date: str | None 
#  single purchase of goods has not start and end date
class CurrenciesEnum(str, Enum):

    euro = 'EUR'
    USDollar = 'USD'

class ProductOrService(BaseModel):
    
    product_service: str
    details: str

class DocumentData(BaseModel):
    creditor: str
    date_of_invoice: str
    period_of_service: PeriodOfService | None
    debitor: str
    total_amount: float
    total_amount_of_taxes_paid: Annotated[float, Ge(0)]
    net_amount: float
    invoice_number: str
    products_services_received: list[ProductOrService] | None
    transaction_currency: str