from datetime import date
import hashlib
from .entity_base import EntityBase

from dataflow.src.models.acc_document import Document, DocumentType


def test_document_computed_alternate_key_matches_manual_hash():
    doc = Document(
        acc_supplier="Contoso",
        acc_attachment="attachment-1",
        acc_document_type=DocumentType.Invoice,
        acc_document_hash_id="h1",
        acc_invoice_date=date(2026, 8, 7),
        acc_net_amount=None,
    )

    expected = hashlib.sha256((doc.acc_supplier + str(doc.acc_invoice_date)).encode("utf-8")).hexdigest()
    assert doc.acc_document_alternatekey == expected

