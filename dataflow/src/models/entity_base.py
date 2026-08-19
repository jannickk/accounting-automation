from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EntityBase(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # the validation alias is required as pydantic would be default exclude the fields
    # starting with an underscore
    modifiedon: Optional[datetime] = None
    owninguser_value: Optional[str] = Field(default=None, alias="_owninguser_value")
    overriddencreatedon: Optional[datetime] = None
    importsequencenumber: Optional[int] = None
    modifiedonbehalfby_value: Optional[str] = Field(default=None, alias="_modifiedonbehalfby_value")
    statecode: Optional[int] = None
    versionnumber: Optional[int] = None
    utcconversiontimezonecode: Optional[int] = None
    createdonbehalfby_value: Optional[str] = Field(default=None, alias="_createdonbehalfby_value")
    modifiedby_value: Optional[str] = Field(default=None, alias="_modifiedby_value")
    createdon: Optional[datetime] = None
    owningbusinessunit_value: Optional[str] = Field(default=None, alias="_owningbusinessunit_value")
    statuscode: Optional[int] = None
    owningteam_value: Optional[str] = Field(default=None, alias="_owningteam_value")
    createdby_value: Optional[str] = Field(default=None, alias="_createdby_value")
    ownerid_value: Optional[str] = Field(default=None, alias="_ownerid_value")
    timezoneruleversionnumber: Optional[int] = None

