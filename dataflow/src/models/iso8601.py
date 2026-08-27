

import datetime

from typing import Annotated

from pydantic import BaseModel, computed_field, field_validator


class ISO8601(BaseModel):
  value: str

  @field_validator('value', mode='before')  
  @classmethod
  def is_correct_iso8601_format(cls, value:str) -> str:
    if isinstance(value, str):
        try:
          datetime.datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Invalid ISO 8601 datetime format")
    return value

  @computed_field
  @property
  def date(self) -> datetime.datetime:
    return datetime.datetime.fromisoformat(self.value)