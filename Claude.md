

## Project Context

Dataflow project to read out attachments of an online exchange server and process each document using Mistral AI document intelligence

## Architecture & Code Map
- `src/dataflow/` - python dataflow code 
- `dataverse/` - The Entity Definitions for Custom Entities used in this Project, i.e. Attachment, document, emails
- `docker/` - The Docker files to build docker images from the src code
- `terraform/` - The terraform code to deploy the App in Azure App Service

## Core Commands
- Install dependencies: `uv pip install -r requirements`



## Behavioral Rules & Workflow
- **Plan First**: Before modifying any logic, output a brief text summary explaining your planned approach, save the implement plans under plans
- **Test Before Finish**: Always run `npm test` successfully before stating that a task is complete.
- **Minimize Edits**: Touch only the files directly relevant to the current task. Do not refactor unrelated code.
- **No Mocking**: Avoid using mock libraries for database tests unless explicitly requested.
