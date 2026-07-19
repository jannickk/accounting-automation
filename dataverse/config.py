from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TENANT_ID: str
    CLIENT_ID: str
    CLIENT_SECRET: str
    ENVIRONMENT_URL: str