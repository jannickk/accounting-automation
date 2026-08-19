from pydantic_settings import BaseSettings


class Config(BaseSettings):
    
    DATAVERSE_TENANT_ID: str 
    DATAVERSE_CLIENT_ID: str 
    DATAVERSE_CLIENT_SECRET: str 
    DATAVERSE_ENVIRONMENT_URL: str 
    GRAPH_API_TENANT_ID: str
    GRAPH_API_CLIENT_ID: str
    GRAPH_API_CLIENT_SECRET: str
    MISTRAL_API_KEY: str
    DATALAKE_STORAGE_CONNECTION_STRING: str
    SHARED_MAILBOX_EMAIL: str
    STORAGE_ACCOUNT_URL: str
    CONTAINER_NAME: str = "accounts-payable"