from azure.storage.filedatalake.aio import DataLakeFileClient as AsyncFileClient
from azure.storage.filedatalake.aio import FileSystemClient as AsyncFileSystemClient
from azure.storage.filedatalake.aio import DataLakeServiceClient as AsyncDataLakeServiceClient
from azure.storage.filedatalake.aio import StorageStreamDownloader as AsyncStorageStreamDownloader
import sys
import json
import aiohttp
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config

async def copy_file_from_one_folder_to_another(config: Config, source_path, target_path, container: str | None = None):
    """
    'source_path' is the path within the filesystem/container
    'target_path' is the path within the filesystem/container
    'container' is the filesystem/container both paths live in; defaults to
    'config.CONTAINER_NAME' when not given explicitly
    """

    file_system = container or config.CONTAINER_NAME

    print(f"Trying to download from path {source_path} in container {file_system}")

    async with AsyncDataLakeServiceClient.from_connection_string(config.DATALAKE_STORAGE_CONNECTION_STRING) as service_client:

        async with service_client.get_file_system_client(file_system = file_system) as filesystem_client:

            source_file_client = filesystem_client.get_file_client(source_path)

            download:AsyncStorageStreamDownloader  = await source_file_client.download_file()

            bytes_data = await download.readall()

            target_file_client = filesystem_client.get_file_client(target_path)

            await target_file_client.upload_data(bytes_data, length=len(bytes_data), overwrite=True)
          

async def download_file_from_azure_storage(config: Config, source_path: str, container: str | None = None) -> bytes:
    """
    Download the content of a single file from the Data Lake as raw bytes.

    'source_path' is the path of the file within the filesystem/container
    'container' is the filesystem/container the file lives in; defaults to
    'config.CONTAINER_NAME' when not given explicitly

    Returns:
        The file content as bytes. To hand it over to 'upload_document_to_datev'
        it has to be base64 encoded first, e.g.
        'document["contentBytes"] = base64.b64encode(content).decode("utf-8")'
    """

    file_system = container or config.CONTAINER_NAME

    print(f"Trying to download from path {source_path} in container {file_system}")

    async with AsyncDataLakeServiceClient.from_connection_string(config.DATALAKE_STORAGE_CONNECTION_STRING) as service_client:

        async with service_client.get_file_system_client(file_system = file_system) as filesystem_client:

            file_client = filesystem_client.get_file_client(source_path)

            if await file_client.exists():

                download: AsyncStorageStreamDownloader = await file_client.download_file()

                return await download.readall()

            else:

                raise Exception(f"Failed to download file {source_path}")

async def upload_to_azure_datalake_storage(base64_data: str, content_type: str, container_name: str, blob_name: str) -> str:
    """
    Upload base64 encoded data to Azure Data Lake Storage Gen2.
    
    Args:
        base64_data: Base64 encoded string of the file content
        content_type: MIME content type for the file
        container_name: Name of the Data Lake filesystem
        blob_name: File path within the filesystem
    
    Returns:
        The URL of the uploaded file in Data Lake Storage
    """
    logger.info(f"Uploading {blob_name} to Data Lake filesystem {container_name}")
    
    file_data = base64.b64decode(base64_data)
    connection_string = os.environ.get("DATALAKE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("Missing DATALAKE_STORAGE_CONNECTION_STRING.")
    
    service_client = DataLakeServiceClient.from_connection_string(connection_string)
    file_system_client = service_client.get_file_system_client(container_name)
    if not file_system_client.exists():
        file_system_client.create_file_system()
    
    # Create any intermediate directories if needed.
    directory, filename = os.path.split(blob_name)
    if directory:
        directory_client = file_system_client.get_directory_client(directory)
        if not directory_client.exists():
            directory_client.create_directory()
        file_client  = directory_client.get_file_client(filename)
    else:
        file_client = file_system_client.get_file_client(filename)
    
    def upload_file():

        if not file_client.exists():
            file_client.create_file()
        file_client.upload_data(file_data, length=len(file_data),overwrite=True)
        file_client.flush_data(len(file_data))
        file_client.set_http_headers(ContentSettings(content_type=content_type))
    
    await asyncio.to_thread(upload_file)
    
    logger.info(f"Successfully uploaded {blob_name} to Data Lake filesystem {container_name}")
    return file_client.url



async def get_access_token_for_graph_api(config: Config) -> str:


    client_id = config.GRAPH_API_CLIENT_ID
    client_secret = config.GRAPH_API_CLIENT_SECRET
    tenant_id = config.GRAPH_API_TENANT_ID
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    async with aiohttp.ClientSession() as session:

        result = await session.post(

            authority + "/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }
        )
        if result.status != 200:
            print(f"Error acquiring token: {result.status}")
            return None

        else:
            response = await result.text()
            response_json = json.loads(response)
            if "access_token" in response_json.keys():
                return response_json["access_token"]
            else:
                print(f"Error acquiring token: {response_json.get('error')}")
                return None
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"Error acquiring token: {result.get('error')}")
        return None