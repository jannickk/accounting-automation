import json
from typing import Optional
import requests
import json
import os
from config import Config
import glob
from typing import Optional, Dict, Any
import requests
from azure.identity import (
    InteractiveBrowserCredential, 
    ClientSecretCredential,
    CertificateCredential,
    AzureCliCredential
)
from PowerPlatform.Dataverse.client import DataverseClient
from PowerPlatform.Dataverse.models.filters import col
from dotenv import load_dotenv
from logger import get_logger




logger = get_logger()

load_dotenv(".env")

config = Config()


credential = ClientSecretCredential(config.TENANT_ID, config.CLIENT_ID, config.CLIENT_SECRET)

client = DataverseClient(config.ENVIRONMENT_URL, credential)

def get_access_token_for_environment():

    return credential.get_token(f"{config.ENVIRONMENT_URL}/.default").token


def get_publisher_id(client: DataverseClient, unique_name: str) -> Optional[str]:
    """Return the publisherid for a publisher unique name, or None if not found."""
    query = (
        client.query.builder("publisher")
        .select("publisherid")
        .where(col("uniquename") == unique_name)
        .top(1)
        .to_dataframe()
    )

    if query.empty:
        return None

    return str(query["publisherid"].iloc[0])


def does_publisher_exist(client, unique_name: str) -> bool:
    """Return True when a publisher with the given unique name exists in the environment."""
    return get_publisher_id(client, unique_name) is not None


def get_solution_id(client: DataverseClient, unique_name: str) -> Optional[str]:
    """Return the solutionid for a solution unique name, or None if not found."""
    query = (
        client.query.builder("solution")
        .select("solutionid")
        .where(col("uniquename") == unique_name)
        .top(1)
        .to_dataframe()
    )

    if query.empty:
        return None

    return str(query["solutionid"].iloc[0])


def does_solution_exists(client, unique_name: str) -> bool:
    """Return True when a solution with the given unique name exists in the environment."""
    return get_solution_id(client, unique_name) is not None


def create_solution(client, solution_data: dict) -> str:
    """Create a solution record and return the created solution id."""
    solution_id = client.records.create("solution", solution_data)
    return str(solution_id)



def create_request_payload(entity:dict):

    request_object = {}

    for key in entity["record"].keys():

        if entity["record"][key]["type"] == "query":
            
            url=config.ENVIRONMENT_URL + "/api/data/v9.2/" + entity["record"][key]["value"]
            response = requests.get(url, headers={"Authorization": f"Bearer {get_access_token_for_environment()}"})
            
            logger.info(f"Lookup query for field {key}: {url} returned status code {response.status_code} with response: {response.text}")
            

            if response.json()["value"]==[]:

                raise ValueError(f"Lookup query for field {key} did not return any records. Response: {response.text} for entity {str(entity)}")

            entity_id = response.json()["value"][0][entity["record"][key]["lookup_field"]]

            request_object[f"{entity["record"][key]["lookup_field"]}@odata.bind"] = f"/{entity["record"][key]["entity_collection"]}({entity_id})"

        else:
            request_object[key] = entity["record"][key]["value"]
    
    return request_object




def get_request_headers(solution_unique_name: str = None) -> Dict[str, str]:
    header = {
                "Authorization": f"Bearer {get_access_token_for_environment()}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
    }
    if solution_unique_name is None:
        return header
    else:
        header["MSCRM.SolutionUniqueName"] = solution_unique_name
        return header


def create_record_via_api(entity: dict, solution_unique_name: str,plan: str = "preview") -> None:

    payload = create_request_payload(entity)
    session = requests.Session()
    session.headers.update(get_request_headers(solution_unique_name))

    if plan == "preview":
        print(f"Preview mode: would create record for entity {entity['record'][entity['primary_name_attribute']]['value']} with payload: {payload}")
        return True

    endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/{entity['entity_collection_name']}"
    # FIX: Do not double-encode JSON
    result = session.post(endpoint, json=payload)

    if result.status_code not in (200, 201, 204):
        print(f"Records created successfully for entity {entity['record'][entity['primary_name_attribute']]['value']} with response: {result.json()}")
        raise ValueError(f"Create record API call failed with status code {result.status_code} and response: {result.text} for entity {str(entity)}")
    else:
        print(f"Record created successfully for entity {entity['record'][entity['primary_name_attribute']]['value']} with response: {result.text}")

def update_record_via_api(entity: dict, record_id: str, plan: str = "preview") -> bool:
    payload = create_request_payload(entity)
    session = requests.Session()

    if plan == "preview":
        print(f"Preview mode: would update record for entity {entity['record'][entity['primary_name_attribute']]['value']} with payload: {payload}")
        return True
    
    print(f"Updating record for entity {entity['record'][entity['primary_name_attribute']]['value']}")

    endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/{entity['entity_collection_name']}({record_id})"
    result = session.patch(endpoint, json=payload)
    return result.status_code == 204

def get_record_id(entity: dict) -> Optional[str]:
    session = requests.Session()
    session.headers.update(get_request_headers())


    value = str(entity["record"][entity["primary_name_attribute"]]["value"])
    value = value.replace("'", "''")  # OData string escaping
    filter_expr = f"{entity['primary_name_attribute']} eq '{value}'"

    endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/{entity['entity_collection_name']}"
    result = session.get(endpoint, params={"$filter": filter_expr})

    if result.status_code != 200:
        return None
    records = result.json().get("value", [])
    if not records:
        return None
    return records[0].get(f"{entity['schema_name']}id")

def does_record_exist(entity: dict) -> bool:
    if get_record_id(entity) is not None:
       return True
    return False


def upsert_record(entity: dict, solution_unique_name: str, plan: str = "preview") -> None:

    if does_record_exist(entity):

        record_id = get_record_id(entity)

        print(f"Record already exists for entity {entity['record'][entity['primary_name_attribute']]['value']}")

        update_record_via_api(entity, record_id, plan)
    else:
        create_record_via_api(entity, solution_unique_name, plan)


def upsert_entity_definition(entity_definition:dict, solution_unique_name: str = None) -> Dict[str, Any]:
    """Create or update an EntityDefinition from raw JSON text.
        Uses `client` for querying existing metadata and the module `config`/`credential`
        to build a session for create/update calls.
    """

    if entity_definition["@odata.type"]== "Microsoft.Dynamics.CRM.EntityMetadata":

        schema_name = entity_definition.get("SchemaName") or entity_definition.get("SchemaName")

        if not schema_name:

            raise ValueError("Entity JSON must include a SchemaName or SchemaName")

        get_endpoint= config.ENVIRONMENT_URL + f"/api/data/v9.2/EntityDefinitions?$filter=SchemaName%20eq%20'{schema_name}'"

        session = requests.Session()
        session.headers.update(get_request_headers(solution_unique_name))

        resp = session.get(get_endpoint)

        session = requests.Session()

        session.headers.update(get_request_headers(solution_unique_name))

        env_url = config.ENVIRONMENT_URL

        if len(resp.json()["value"])==0:

            print(f"No existing EntityDefinition found with schema name {schema_name}. Creating new EntityDefinition.")

            endpoint = f"{env_url}/api/data/v9.2/EntityDefinitions"

            resp = session.post(endpoint, json=entity_definition)

            try:
                resp.raise_for_status()
            except Exception:

                print(f"Failed to create EntityDefinition with schema name {schema_name}. Response: {resp.text}")
                return {"action": "create_failed", "id": None, "response": resp.text}
                    # re-query to obtain metadata id
            escaped_schema_name = schema_name.replace("'", "''")
            metadata_lookup_resp = session.get(
                f"{env_url}/api/data/v9.2/EntityDefinitions?$filter=SchemaName%20eq%20'{escaped_schema_name}'"
            )
            metadata_lookup_resp.raise_for_status()
            metadata_items = metadata_lookup_resp.json().get("value", [])
            created_id = None if not metadata_items else str(metadata_items[0].get("MetadataId"))

            print(f"Created EntityDefinition with schema name {schema_name} and MetadataId {created_id}")

            if len(entity_definition.get("Keys", []))> 0:
                print(f"EntityDefinition {schema_name} has Keys defined, Going in create keys in second step ")

                for key in entity_definition.get("Keys", []):
                    key_payload = {
                        "@odata.type": "#Microsoft.Dynamics.CRM.EntityKeyMetadata",
                        "SchemaName": key["SchemaName"],
                        "SchemaName": key.get("SchemaName", key["SchemaName"]),
                        "DisplayName": key.get("DisplayName", {"LocalizedLabels": [{"Label": key["SchemaName"], "LanguageCode": 1033}]}),
                        "KeyAttributes": key["KeyAttributes"]
                    }
                    key_endpoint = f"{env_url}/api/data/v9.2/EntityDefinitions({created_id})/Keys"
                    key_resp = session.post(key_endpoint, json=key_payload)
                    try:
                        key_resp.raise_for_status()
                        print(f"Created Key {key['SchemaName']} for EntityDefinition {schema_name}")
                    except Exception:
                        print(f"Failed to create Key {key['SchemaName']} for EntityDefinition {schema_name}. Response: {key_resp.text}")
        

                    print("Successfully created Keys for EntityDefinition " + schema_name + " with response: " + key_resp.text)

            ## Even when keys are defined the schema they are ignored

        else:
            
            print(f"Existing EntityDefinition found with schema name {schema_name}. Updating existing EntityDefinition.")


            ## This justs sync the EntityMetadata but does not handle addition/deletion of attributes, which would require additional logic to compare existing attributes with the provided schema and make additional API calls to add/delete attributes as needed.
            sync_entity_attributes_with_schema(schema_name, entity_definition, solution_unique_name) 
   

    else:

        print("JSON file is not an entity definition")

def upsert_relationship_definition(relationship_definition:dict, solution_unique_name: str = None) -> Dict[str, Any]:

    schema_name = relationship_definition.get("SchemaName")
    
    if not schema_name:
    
        raise ValueError("Relationship JSON must include a SchemaName")
    
    get_endpoint= config.ENVIRONMENT_URL + f"/api/data/v9.2/RelationshipDefinitions?$filter=SchemaName%20eq%20'{schema_name}'"
    
    session = requests.Session()
    session.headers.update(get_request_headers(solution_unique_name))
    
    resp = session.get(get_endpoint)

    print("obtained the following response from the relationship endpoint")
    print(resp.json())
    
    if len(resp.json()["value"])==0:
    
        print(f"No existing Realtionship Deinfition found with schema name {schema_name}. Creating new Relationship Definition.")
    
        endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/RelationshipDefinitions"
    
        resp = session.post(endpoint, json=relationship_definition)
    
        try:

            resp.raise_for_status()

        except Exception:
    
            print(f"Failed to create RelationshipDefinition with schema name {schema_name}. Response: {resp.text}")
    
        
        # re-query to obtain metadata id
        escaped_schema_name = schema_name.replace("'", "''")
        metadata_lookup_resp = session.get(f"{config.ENVIRONMENT_URL}/api/data/v9.2/RelationshipDefinitions?$filter=SchemaName%20eq%20'{escaped_schema_name}'")
        metadata_lookup_resp.raise_for_status()
        metadata_items = metadata_lookup_resp.json().get("value", [])
        created_id = None if not metadata_items else str(metadata_items[0].get("MetadataId"))
    
        print(f"Created Relationship Definition with schema name {schema_name} and MetadataId {created_id}")

    else:

        print("Relationhsip Definition already exists")
    
    

def process_entity_definitions_folder(client, folder_path: str = None, solution_unique_name: str = None) -> Dict[str, Dict[str, Any]]:
    """Process all .json files in the entity-definitions folder and upsert them.

        Returns a mapping of filename -> result dict from `upsert_entity_definition`.
    """
    if folder_path is None:
        folder_path = os.path.join(os.path.dirname(__file__), "entity-definitions")

    results: Dict[str, Dict[str, Any]] = {}
    for path in glob.glob(os.path.join(folder_path, "*.json")):
        
        with open(path, "r", encoding="utf-8") as fh:

            text = fh.read()

            try:
                res = upsert_entity_definition(client, text, solution_unique_name)
            except Exception as e:
                res = {"action": "error", "error": str(e)}
            results[os.path.basename(path)] = res
    
    return results


def sync_entity_attributes_with_schema(entity_logical_name: str, entity_definition: dict, solution_unique_name: str = None):
    """
    Syncs the attributes of an EntityDefinition in Dataverse with the provided schema:
    - Adds missing attributes that are in schema but not in Dataverse
    - Deletes attributes that are in Dataverse but not in schema
    Args:
        entity_logical_name (str): Logical name of the entity (e.g., 'acc_creditor')
        schema_attributes (list): List of attribute logical names (str) that should exist
        solution_unique_name (str, optional): Solution unique name for header if needed
    """
    # 1. Get the EntityDefinition MetadataId
    get_endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/EntityDefinitions?$filter=SchemaName eq '{entity_logical_name}'"

    ## Setup HTTP session
    session = requests.Session()
    session.headers.update(get_request_headers(solution_unique_name))


    resp = session.get(get_endpoint)
    resp.raise_for_status()
    values = resp.json().get('value', [])
    if not values:
        raise ValueError(f"EntityDefinition for {entity_logical_name} not found.")
    
    metadata_id = values[0]['MetadataId']

    # 2. Get all current attributes from the API
    attr_endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/EntityDefinitions({metadata_id})/Attributes"
    attr_resp = session.get(attr_endpoint)
    attr_resp.raise_for_status()

    print(f"Received following attributes for entity {entity_logical_name}: {attr_resp.text}")

    current_attrs = attr_resp.json().get('value', [])

  
    # Exclude LookupAttribute Metadata because they are created by creating relationships

    current_attr_names = {a['SchemaName'] for a in current_attrs}

    schema_attr_names = {a['SchemaName'] for a in entity_definition.get('Attributes', [])}


    diff_attr_names = [schema_name for schema_name in schema_attr_names if not schema_name in current_attr_names]

    attr_to_add = [attr for attr in entity_definition.get('Attributes', []) if attr['SchemaName'] in diff_attr_names ]


    # 3. Add missing attributes
    for attr in attr_to_add:

        # Minimal attribute payload, customize as needed

        print("adding missing attribute " + attr['SchemaName'] + " to entity " + entity_logical_name)

        payload = attr

        create_attr_endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/EntityDefinitions({metadata_id})/Attributes"
        create_resp = session.post(create_attr_endpoint, json=payload)
        try:
            create_resp.raise_for_status()
            print(f"Added attribute {attr['SchemaName'] }")
        except Exception:
            print(f"Failed to add attribute {attr['SchemaName'] }: {create_resp.text}")

    # 4. Delete attributes not in schema
    for attr in current_attrs:

        print("checking attribute " + attr['SchemaName'] + " in entity " + entity_logical_name)

        if attr['SchemaName'] not in schema_attr_names:

            if attr["IsCustomAttribute"] == True:


                ## Fiter out Lookup Up Columns (as these are created via Realtionships)
                ## For each lookup column there are actually two columns created
                ## the actual Lookup column with the schema name as specified in the Relationship
                ## and a column with <SchemaName>Name. These have the property "isLogical" set to true

                print(f"Attribute {attr['SchemaName']} is not in schema and is a custom attribute, deleting it.")

                if "@odata.type" in attr.keys():

                    if "Microsoft.Dynamics.CRM.LookupAttributeMetadata" in attr["@odata.type"] or attr["IsLogical"]== True:


                        print(f"Attribute {attr['SchemaName']} is associated with a lookup, skipping")
  
                    else:

                        print("deleting attribute " + attr['SchemaName'] + " from entity " + entity_logical_name)
                        
                        attr_id = attr['MetadataId']
                        
                        delete_endpoint = f"{config.ENVIRONMENT_URL}/api/data/v9.2/EntityDefinitions({metadata_id})/Attributes({attr_id})"
                        
                        del_resp = session.delete(delete_endpoint)
                        
                        try:
                            del_resp.raise_for_status()
                            print(f"Deleted attribute {attr['SchemaName']}")
                        except Exception:
                            print(f"Failed to delete attribute {attr['SchemaName']}: {del_resp.text}")
            else:

                print(f"Attribute {attr['SchemaName']} is not in schema but is a system attribute, skipping deletion.")

        else:

            # When the entity attribiute / table column appears in the schema, make sure that the attribute properties
            if attr["IsCustomAttribute"] == True:

                print(f"Attribute {attr['SchemaName']} is defined in schema and present in Table, Updating it")

                ## Find the current attribute definition.
                payload = [attr_definition for attr_definition in entity_definition.get('Attributes', []) if attr_definition["SchemaName"] == attr["SchemaName"]]

                attr_id = attr['MetadataId']

                update_endpoint =  f"{config.ENVIRONMENT_URL}/api/data/v9.2/EntityDefinitions({metadata_id})/Attributes({attr_id})"
                update_resp = session.put(update_endpoint, json=payload[0])

                try:
                    update_resp.raise_for_status()
                except:
                    print(f"Failed to Update attribute {attr['SchemaName']}: {update_resp.text}")