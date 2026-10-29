from decimal import Decimal

import pytest

from app import extractor
from conftest import LOCKED, UNLOCKED, PASSWORD


def test_detects_encryption():
    assert extractor.is_encrypted(LOCKED.read_bytes())
    assert not extractor.is_encrypted(UNLOCKED.read_bytes())


def test_wrong_password_rejected():
    with pytest.raises(ValueError, match="password"):
        extractor.decrypt_to_bytes(LOCKED.read_bytes(), "WRONG")


def test_non_pdf_rejected():
    with pytest.raises(ValueError, match="readable PDF"):
        extractor.decrypt_to_bytes(b"not a pdf", None)


def test_locked_and_unlocked_parse_identically():
    a = extractor.parse(extractor.decrypt_to_bytes(LOCKED.read_bytes(), PASSWORD))
    b = extractor.parse(extractor.decrypt_to_bytes(UNLOCKED.read_bytes(), None))
    assert a and [t.as_dict() for t in a] == [t.as_dict() for t in b]


def test_sample_reconciles_and_amounts_are_positive():
    pdf = extractor.decrypt_to_bytes(LOCKED.read_bytes(), PASSWORD)
    txns = extractor.parse(pdf)
    check = extractor.balance_check(txns, extractor.extract_opening(pdf))
    assert check["reconciles"], check
    assert all(t.amount > 0 and t.txn_type in ("debit", "credit") for t in txns)
    assert all(t.category in extractor.CATEGORIES for t in txns)


def test_parsed_txn_round_trips():
    t = extractor.parse(extractor.decrypt_to_bytes(UNLOCKED.read_bytes(), None))[0]
    back = extractor.ParsedTxn.from_dict(t.as_dict())
    assert back == t and isinstance(back.amount, Decimal)


@pytest.mark.parametrize("desc, method, category, kind", [
    ("ATM WDL ATM CASH 1234 MG ROAD", "ATM", "Cash", "self"),
    ("SMS CHARGES FOR QTR", "FEE", "Bank Fees", "bank"),
    ("TO TRANSFER-UPI/DR/412345678901/BUNDL TECHNOLOGIES/YESB/swiggy@ybl/Payment", "UPI", "Food & Dining", "merchant"),
    ("TO TRANSFER-UPI/DR/412345678902/RAHUL SHARMA/SBIN/rahul@oksbi/", "UPI", "Transfer · Person", "person"),
])
def test_normalise(desc, method, category, kind):
    m, _merchant, c, k = extractor.normalise(desc)
    assert (m, c, k) == (method, category, kind)
