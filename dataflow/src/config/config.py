from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    
    DATAVERSE_TENANT_ID: str = Field(..., description="The EntraID Tenant ID of the Dataverse Envrionment")
    DATAVERSE_CLIENT_ID: str 
    DATAVERSE_CLIENT_SECRET: str 
    DATAVERSE_ENVIRONMENT_URL: str 
    DATAVERSE_MCP_ENDPOINT: str
    GRAPH_API_TENANT_ID: str
    GRAPH_API_CLIENT_ID: str
    GRAPH_API_CLIENT_SECRET: str
    MISTRAL_API_KEY: str
    DATALAKE_STORAGE_CONNECTION_STRING: str
    SHARED_MAILBOX_EMAIL: str
    STORAGE_ACCOUNT_URL: str
    CONTAINER_NAME: str = "accounts-payable"
    MISTRAL_MCP_CLIENT_ID: str
    MISTRAL_MCP_CLIENT_SECRET: str
    UPLOAD_INBOX_EMAIL: str
    SENDER_EMAIL_DATEV: str