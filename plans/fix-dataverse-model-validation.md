# Fix plan: Dataverse payload validation for entity models

## Problem
Dataverse payloads include system metadata fields such as `_owninguser_value`, `_modifiedby_value`, and primary-key fields like `acc_emailid`. The model subclasses currently override the base `EntityBase` configuration with `extra = "forbid"`, which rejects those fields during `model_validate()`.

## Approach
1. Keep the base entity behavior permissive for Dataverse metadata while preserving typed model fields.
2. Allow Dataverse field aliases such as `acc_emailid`/`acc_attachmentid`/`acc_documentid` to populate the canonical camel-case model attributes.
3. Validate the fix with a focused unit test that exercises `Email.model_validate()` against a Dataverse-style payload.

## Files to touch
- `dataflow/src/models/entity_base.py`
- `dataflow/src/models/acc_email.py`
- `dataflow/src/models/acc_attachment.py`
- `dataflow/src/models/acc_document.py`
- `dataflow/src/models/test_emails.py` (or a new focused test)
