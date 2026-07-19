from typing import Optional
from datetime import datetime
from pydantic import BaseModel,Field
import hashlib
from PowerPlatform.Dataverse.models import UpsertItem
from PowerPlatform.Dataverse.client import DataverseClient




class Email(BaseModel):

    entity_logical_name: str = Field(exclude=True, default="acc_email")
  
    acc_outlook_emailid: str
    acc_isduplicateof: Optional[str] = None
    acc_subject: Optional[str] = None
    acc_numofattachments: Optional[int] = None
    acc_receiveddatetime: datetime
    acc_receiveddatetime_year: int
    acc_receiveddatetime_month: int
    acc_ingesteddatetime: datetime
    acc_processeddatetime: datetime
    acc_hashid: str
    acc_sender_name: Optional[str] = None
    acc_sender_address: Optional[str] = None
    acc_from_name: Optional[str] = None
    acc_from_address: Optional[str] = None
    acc_torecipients_json: Optional[str] = None
    acc_body_contenttype: Optional[str] = None
    acc_body_contentbytes_b64: Optional[str] = None
    acc_sender_json: Optional[str] = None

    class Config:
        extra = "forbid"

    def write_to_dataverse(self, client: DataverseClient):
        """
        Write (upsert) the email record to Dataverse using the provided Dataverse client.

        The record is identified by the ``acc_hashid`` alternate key, so re-ingesting the
        same email updates the existing row instead of creating a duplicate. Values are
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



class EmailFactory:
    @staticmethod
    def create_email(email: dict) -> Email:
        return Email(
            acc_outlook_emailid=email.get("id"),
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