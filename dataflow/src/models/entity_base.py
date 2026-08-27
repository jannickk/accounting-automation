from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class EntityBase(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # the validation alias is required as pydantic would be default exclude the fields
    # starting with an underscore
    modifiedon: Optional[datetime] = None
    owninguser: Optional[str] = Field(
                                            default=None, 
                                            validation_alias=AliasChoices("_owninguser_value","owninguser_value"),
                                            foreign_key="systemuser.systemuserid", 
                                            serialization_alias= "ownerid"
                                            )
    overriddencreatedon: Optional[datetime] = None
    importsequencenumber: Optional[int] = None
    modifiedonbehalfby: Optional[str] = Field(
                                                    default=None, 
                                                    validation_alias=AliasChoices("_modifiedonbehalfby_value","modifiedonbehalfby_value"),
                                                    foreign_key="systemuser.systemuserid",
                                                    serialization_alias="modifiedonbehafby"
                                                    )
    statecode: Optional[int] = None
    versionnumber: Optional[int] = None
    utcconversiontimezonecode: Optional[int] = None
    createdonbehalfby: Optional[str] = Field(default=None,
                                                     validation_alias=AliasChoices("_createdonbehalfby_value","createdonbehalfby_value"),
                                                     foreign_key="systemuser.systemuserid",
                                                     serialiaztion_alias="createdonbehalfby"
                                                     )
    modifiedby: Optional[str] = Field(
                                                        default=None,
                                                         validation_alias=AliasChoices("_modifiedby_value","modifiedby_value"),
                                                         foreign_key="systemuser.systemuserid",
                                                         serialiaztion_alias="modifiedby"
                                                         )
    createdon: Optional[datetime] = None

    owningbusinessunit: Optional[str] = Field(
                                                    default=None, 
                                                    validation_alias=AliasChoices("_owningbusinessunit_value","owningbusinessunit_value"),
                                                    foreign_key="businessunit.businessunitid")
    statuscode: Optional[int] = None
    owningteam: Optional[str] = Field(default=None, validation_alias=AliasChoices("_owningteam_value","owningteam_value"),foreign_key="team.teamid")
    createdby: Optional[str] = Field(default=None, validation_alias=AliasChoices("_createdby_value","createdby_value"),foreign_key="systemuser.systemuserid")
    ownerid: Optional[str] = Field(default=None, validation_alias=AliasChoices("_ownerid_value","ownerid_value"),foreign_key="systemuser.systemuserid")
    timezoneruleversionnumber: Optional[int] = None