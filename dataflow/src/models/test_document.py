from datetime import date
from decimal import Decimal
import hashlib

import pytest
from pydantic import ValidationError

from .entity_base import EntityBase
from .acc_document import Document


# The three lookups on acc_document are all ApplicationRequired, so every valid
# Document needs them. These stand in for the GUIDs Dataverse hands back for the
# related acc_creditor / acc_attachment / transactioncurrency records.
CREDITOR_ID = "8f0d0a44-1e94-f111-8076-7ced8d2ca142"
ATTACHMENT_ID = "ecb30fd1-1e94-f111-8076-7ced8d2ca142"
CURRENCY_ID = "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8"


@pytest.fixture
def minimal_document() -> Document:
    """A Document carrying only the fields the schema marks as required."""

    return Document(
        acc_creditorId=CREDITOR_ID,
        acc_attachmentId=ATTACHMENT_ID,
        acc_transactioncurrencyId=CURRENCY_ID,
    )


@pytest.fixture
def full_document() -> Document:
    """A Document with every optional attribute populated."""

    return Document(
        acc_creditorId=CREDITOR_ID,
        acc_attachmentId=ATTACHMENT_ID,
        acc_transactioncurrencyId=CURRENCY_ID,
        acc_invoice_date=date(2026, 8, 7),
        acc_net_amount=Decimal("100.50"),
        acc_vat_amount=Decimal("19.10"),
        acc_gross_amount=Decimal("119.60"),
        acc_total_amount=Decimal("119.60"),
        acc_invoice_id="INV-2026-0815",
        acc_supplier_tax_id="DE123456789",
        acc_supplier_iban="DE89370400440532013000",
        acc_invoice_year=2026,
        acc_invoice_month=8,
        acc_invoice_day=7,
        acc_period_of_service_month=7,
        acc_period_of_service_start_date=date(2026, 7, 1),
        acc_period_of_service_end_date=date(2026, 7, 31),
        acc_supplier_email="billing@contoso.example",
        acc_supplier_address="Musterstr. 1\n10115 Berlin\nGermany",
        acc_supplier_name="Contoso GmbH",
        acc_supplier_registration="HRB 12345 B",
    )


def test_document_is_entity_base_with_expected_logical_name(minimal_document: Document):
    """
    Document must inherit the Dataverse system fields from EntityBase and carry
    the logical name used for every OData call.
    """

    assert isinstance(minimal_document, EntityBase)
    assert minimal_document.entity_logical_name == "acc_document"


def test_document_requires_all_three_lookups():
    """
    acc_creditorId, acc_attachmentId and acc_transactioncurrencyId are all
    ApplicationRequired lookups, so omitting any of them must fail validation.
    """

    required_fields = {
        "acc_creditorId": CREDITOR_ID,
        "acc_attachmentId": ATTACHMENT_ID,
        "acc_transactioncurrencyId": CURRENCY_ID,
    }

    for omitted in required_fields:

        kwargs = {name: value for name, value in required_fields.items() if name != omitted}

        with pytest.raises(ValidationError) as exc_info:
            Document(**kwargs)

        # The error must point at the field that was left out
        assert omitted in str(exc_info.value)


def test_document_optional_fields_default_to_none(minimal_document: Document):
    """Everything the schema marks as RequiredLevel None must default to None."""

    assert minimal_document.acc_documentId is None
    assert minimal_document.acc_invoice_date is None
    assert minimal_document.acc_net_amount is None
    assert minimal_document.acc_vat_amount is None
    assert minimal_document.acc_gross_amount is None
    assert minimal_document.acc_total_amount is None
    assert minimal_document.acc_invoice_id is None
    assert minimal_document.acc_supplier_tax_id is None
    assert minimal_document.acc_supplier_iban is None
    assert minimal_document.acc_invoice_year is None
    assert minimal_document.acc_invoice_month is None
    assert minimal_document.acc_invoice_day is None
    assert minimal_document.acc_period_of_service_month is None
    assert minimal_document.acc_period_of_service_start_date is None
    assert minimal_document.acc_period_of_service_end_date is None
    assert minimal_document.acc_supplier_email is None
    assert minimal_document.acc_supplier_address is None
    assert minimal_document.acc_supplier_name is None
    assert minimal_document.acc_supplier_registration is None

    # System fields inherited from EntityBase are only populated on read
    assert minimal_document.modifiedon is None
    assert minimal_document.createdon is None
    assert minimal_document.ownerid_value is None


def test_document_computed_alternate_key_matches_manual_hash(full_document: Document):
    """The alternate key is sha256(creditor id + invoice date)."""

    expected = hashlib.sha256(
        (full_document.acc_creditorId + str(full_document.acc_invoice_date)).encode("utf-8")
    ).hexdigest()

    assert full_document.acc_document_alternatekey == expected
    assert len(full_document.acc_document_alternatekey) == 64


def test_document_alternate_key_is_deterministic_and_discriminating():
    """
    Two documents from the same creditor with the same invoice date collapse onto
    the same alternate key (that is what makes the upsert idempotent), while a
    different creditor or a different date must produce a different key.
    """

    base = dict(
        acc_creditorId=CREDITOR_ID,
        acc_attachmentId=ATTACHMENT_ID,
        acc_transactioncurrencyId=CURRENCY_ID,
        acc_invoice_date=date(2026, 8, 7),
    )

    same = Document(**base)
    duplicate = Document(**{**base, "acc_invoice_id": "a-different-invoice-number"})
    other_creditor = Document(**{**base, "acc_creditorId": CURRENCY_ID})
    other_date = Document(**{**base, "acc_invoice_date": date(2026, 8, 8)})

    assert same.acc_document_alternatekey == duplicate.acc_document_alternatekey
    assert same.acc_document_alternatekey != other_creditor.acc_document_alternatekey
    assert same.acc_document_alternatekey != other_date.acc_document_alternatekey


def test_document_alternate_key_tolerates_missing_invoice_date(minimal_document: Document):
    """
    acc_invoice_date is optional, so the alternate key has to stay computable when
    the extraction did not find a date.
    """

    expected = hashlib.sha256((CREDITOR_ID + "None").encode("utf-8")).hexdigest()

    assert minimal_document.acc_document_alternatekey == expected


@pytest.mark.parametrize(
    "field_name",
    ["acc_net_amount", "acc_vat_amount", "acc_gross_amount", "acc_total_amount"],
)
def test_document_amount_bounds_are_enforced(field_name: str):
    """All four decimal amounts are constrained to 0 .. 99,000,000,000."""

    base = dict(
        acc_creditorId=CREDITOR_ID,
        acc_attachmentId=ATTACHMENT_ID,
        acc_transactioncurrencyId=CURRENCY_ID,
    )

    # Negative amounts are rejected
    with pytest.raises(ValidationError):
        Document(**base, **{field_name: Decimal("-0.01")})

    # Amounts above the schema MaxValue are rejected
    with pytest.raises(ValidationError):
        Document(**base, **{field_name: Decimal("99000000000.01")})

    # The bounds themselves are inclusive
    assert getattr(Document(**base, **{field_name: Decimal("0")}), field_name) == Decimal("0")
    assert getattr(
        Document(**base, **{field_name: Decimal("99000000000")}), field_name
    ) == Decimal("99000000000")


@pytest.mark.parametrize(
    "field_name, max_length",
    [
        ("acc_invoice_id", 250),
        ("acc_supplier_tax_id", 100),
        ("acc_supplier_iban", 50),
        ("acc_supplier_email", 320),
        ("acc_supplier_address", 4000),
        ("acc_supplier_name", 250),
        ("acc_supplier_registration", 250),
    ],
)
def test_document_string_max_lengths_match_schema(field_name: str, max_length: int):
    """String attributes must not accept more characters than Dataverse stores."""

    base = dict(
        acc_creditorId=CREDITOR_ID,
        acc_attachmentId=ATTACHMENT_ID,
        acc_transactioncurrencyId=CURRENCY_ID,
    )

    # Exactly at the limit is fine
    at_limit = Document(**base, **{field_name: "x" * max_length})
    assert len(getattr(at_limit, field_name)) == max_length

    # One character over the limit is rejected
    with pytest.raises(ValidationError):
        Document(**base, **{field_name: "x" * (max_length + 1)})


def test_document_model_validate_accepts_dataverse_payload():
    """
    A record read back from Dataverse arrives with lower-cased attribute names,
    underscore-prefixed system lookups and extra OData annotations. All of that
    must validate onto the model.
    """

    payload = {
        "@odata.etag": 'W/"12345678"',
        "acc_documentid": "7d2a6f31-1e94-f111-8076-7ced8d2ca142",
        "acc_document_alternatekey": "alt-key-123",
        "acc_creditorId": CREDITOR_ID,
        "acc_attachmentId": ATTACHMENT_ID,
        "acc_transactioncurrencyId": CURRENCY_ID,
        "acc_invoice_id": "INV-2026-0815",
        "acc_invoice_date": "2026-08-07",
        "acc_net_amount": "100.50",
        "acc_vat_amount": "19.10",
        "acc_gross_amount": "119.60",
        "acc_supplier_name": "Contoso GmbH",
        "createdon": "2026-08-07T12:00:00+00:00",
        "modifiedon": "2026-08-08T09:30:00+00:00",
        "statecode": 0,
        "statuscode": 1,
        "versionnumber": 987654,
        "_owninguser_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_modifiedonbehalfby_value": None,
        "_createdonbehalfby_value": None,
        "_modifiedby_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_owningbusinessunit_value": "5ac5d729-2e30-f111-88b3-6045bddeaf59",
        "_owningteam_value": None,
        "_createdby_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
        "_ownerid_value": "3b1d3ac8-ab35-f111-88b4-000d3ab76fd8",
    }

    document = Document.model_validate(payload)

    # The lower-cased primary key alias is picked up
    assert document.acc_documentId == payload["acc_documentid"]

    # Strings are coerced into the declared python types
    assert document.acc_invoice_date == date(2026, 8, 7)
    assert document.acc_net_amount == Decimal("100.50")

    # System fields land on the EntityBase attributes
    assert document.ownerid_value == payload["_ownerid_value"]
    assert document.createdby_value == payload["_createdby_value"]
    assert document.versionnumber == 987654
    assert document.modifiedon is not None

    # Unknown OData annotations are ignored rather than raising
    assert not hasattr(document, "@odata.etag")


def test_document_convert_to_odata_payload(full_document: Document):
    """
    convert_to_odata_payload must turn every lookup into an @odata.bind entry,
    drop the client-side-only fields, and JSON-serialise dates and decimals.
    """

    payload = full_document.convert_to_odata_payload()

    assert isinstance(payload, dict)

    # Client-side-only field is excluded
    assert "entity_logical_name" not in payload

    # Lookups are bound by URL, never sent as raw values
    assert payload["acc_creditorId@odata.bind"] == f"/acc_creditors({CREDITOR_ID})"
    assert payload["acc_attachmentId@odata.bind"] == f"/acc_attachments({ATTACHMENT_ID})"
    assert "acc_creditorId" not in payload
    assert "acc_attachmentId" not in payload
    assert "acc_transactioncurrencyId" not in payload
    assert "acc_transactioncurrencyId@odata.bind" in payload

    # The alternate key needed for the upsert URL is present
    assert payload["acc_document_alternatekey"] == full_document.acc_document_alternatekey
    assert len(payload["acc_document_alternatekey"]) == 64

    # Dates and decimals are JSON-serialised
    assert payload["acc_invoice_date"] == "2026-08-07"
    assert payload["acc_period_of_service_start_date"] == "2026-07-01"
    assert payload["acc_net_amount"] == "100.50"

    # Plain scalars pass through untouched
    assert payload["acc_invoice_id"] == "INV-2026-0815"
    assert payload["acc_invoice_year"] == 2026
    assert payload["acc_supplier_name"] == "Contoso GmbH"


def test_document_convert_to_odata_payload_drops_unset_optionals(minimal_document: Document):
    """
    The payload is built with exclude_none, so attributes the extraction did not
    fill must be absent instead of being sent as explicit nulls.
    """

    payload = minimal_document.convert_to_odata_payload()

    for omitted in ("acc_invoice_date", "acc_net_amount", "acc_supplier_name", "acc_documentId"):
        assert omitted not in payload

    # ... while the required lookups and the alternate key are still there
    assert "acc_creditorId@odata.bind" in payload
    assert "acc_attachmentId@odata.bind" in payload
    assert "acc_transactioncurrencyId@odata.bind" in payload
    assert "acc_document_alternatekey" in payload


@pytest.mark.xfail(
    reason=(
        "convert_to_odata_payload pluralises the target entity by appending 's', which "
        "yields /transactioncurrencys(...). The Dataverse entity set for "
        "transactioncurrency is /transactioncurrencies(...), so this bind will 404."
    ),
    strict=True,
)
def test_document_transaction_currency_binds_to_correct_entity_set(full_document: Document):
    """Guards the known-wrong pluralisation of the transactioncurrency entity set."""

    payload = full_document.convert_to_odata_payload()

    assert payload["acc_transactioncurrencyId@odata.bind"] == f"/transactioncurrencies({CURRENCY_ID})"
