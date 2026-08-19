import glob

from azure.identity import (
    InteractiveBrowserCredential, 
    ClientSecretCredential,
    CertificateCredential,
    AzureCliCredential
)
from PowerPlatform.Dataverse.client import DataverseClient
from config import Config
from dotenv import load_dotenv
from solutions.accounting import *
from logger import get_logger
from pandas import DataFrame as df
import json
import requests
import utils
import os
import argparse

load_dotenv(".env")

if __name__=="__main__":


    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", help="whether to preview changes or actually apply them", choices=["preview", "apply"])
    args = parser.parse_args()

    plan=args.plan


    
    if not plan:

        raise ValueError("Please specify a plan: preview or apply")
    
    print(f"Running with plan: {plan}")

    logger = get_logger()

    config = Config()

    credential = ClientSecretCredential(config.TENANT_ID, config.CLIENT_ID, config.CLIENT_SECRET)

    client = DataverseClient(config.ENVIRONMENT_URL, credential)


    if not utils.does_publisher_exist(client, publisher["uniquename"]):

        publisher_id =  utils.create_publisher(client, publisher)

    else:
        publisher_id = utils.get_publisher_id(client, publisher["uniquename"])

    if not utils.does_solution_exists(client, get_solution(publisher_id)["uniquename"]):
        
        utils.create_solution(client, get_solution(publisher_id))

    solution_to_create = get_solution(publisher_id)

    print(f"looking for solution: {solution_to_create}")

    if not utils.does_solution_exists(client, solution_to_create["uniquename"]):
        solution_id = utils.create_solution(client, solution_to_create)
    else: 
        solution_id = utils.get_solution_id(client, solution_to_create["uniquename"])

    ############################################################
    ## Go through entity definitions and create them if they don't exist. This is required before we can upsert records to those tables.
    ##############################################################

    base_dir = os.path.dirname(os.path.abspath(__file__))
    entity_definitions_dir = os.path.join(base_dir, "entity-definitions")
    relationship_definitions_dir = os.path.join(base_dir, "relationship-definitions")
    entities_dir = os.path.join(base_dir, "entities")

    if os.path.exists(entity_definitions_dir) and os.path.isdir(entity_definitions_dir):

        folders:list[str] = os.listdir(entity_definitions_dir)

        # Sort so that we create entities in the correct order
        folders.sort()

        for folder in folders:  

            files = glob.glob(os.path.join(entity_definitions_dir, folder, "*.json"))

            for file in files:

                with open(file, "r", encoding="utf-8") as f:
                    text = f.read()
                    entity = json.loads(text)
                    res = utils.upsert_entity_definition(entity, solution_to_create["uniquename"])

    
    if os.path.exists(relationship_definitions_dir) and os.path.isdir(relationship_definitions_dir):

        folders:list[str] = os.listdir(relationship_definitions_dir)

        # Sort so that we create entities in the correct order
        folders.sort()

        for folder in folders:  

            files = glob.glob(os.path.join(relationship_definitions_dir, folder, "*.json"))

            for file in files:

                with open(file, "r", encoding="utf-8") as f:
                    text = f.read()
                    entity = json.loads(text)
                    res = utils.upsert_relationship_definition(entity, solution_to_create["uniquename"])

    if os.path.exists(entities_dir) and os.path.isdir(entities_dir):

        logger.info(f"Found entities directory: {entities_dir}")
        entity_folders:list[str] = os.listdir(entities_dir)

        # Sort so that we create entities in the correct order
        entity_folders.sort()

        for folder in entity_folders:  

            files = glob.glob(os.path.join(entities_dir, folder, "**", "*.json"), recursive=True)

            for file in files:
                with open(file, "r", encoding="utf-8") as f:
                    text = f.read()
                    entity = json.loads(text)
                    res = utils.upsert_record(entity, solution_to_create["uniquename"], plan=plan)


