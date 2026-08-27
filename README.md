

## Integrate AI into your structured dataflows

This repo contains a show case how incoming documents for accounts-payables are extarcted using MIstral AI latest flagship multimodel model to extract 
structured information. 


## High-level architecture


All Information is stored in Microsoft Dataverse.


## Agents 

The agent schema-syncer` keeps the schemas between Dataverse Schema specification and the Pydantic Models 

######

1) All Emails are checked in an Outlook inbox

2) The attachment is retrieved and stored in a bronze data layer partitioned by date-month

3) The bronze to silver job submits each document to Mistral Document AI and extracts relevant information from the invoice

4) the extracted information is stored in a silver invoice table and documents are copied to a silver storage location partionied by supplier and 


Common Issues

The queries for the tools turned out to be  explicetly states the queries to use because depending on the Run, some queries were not corretly constructed

## 

In order to use the MCP Connection to Azure Storage, you need authenticate uisng in order to provide the default azure credential `az login --use-device-code`